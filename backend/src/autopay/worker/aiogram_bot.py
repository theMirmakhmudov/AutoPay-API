import logging
from typing import Any, Dict
from aiogram import Bot, Dispatcher, F, Router, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault, CallbackQuery, InlineKeyboardButton, Message, InputRichMessage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from autopay.core.config import settings
from autopay.core.database import SessionLocal
from autopay.core.encryption import encrypt_session, generate_api_key, generate_webhook_secret
from autopay.models.payment import AllowedMerchant, Merchant, PaymentIntent, ProcessedPayment, UnparsedMessage
logger = logging.getLogger(__name__)
API_ID = settings.TELEGRAM_API_ID
API_HASH = settings.TELEGRAM_API_HASH
_client_manager = None
user_states: Dict[int, Dict[str, Any]] = {}


def set_client_manager(manager):
    global _client_manager
    _client_manager = manager


bot = Bot(token=settings.MANAGEMENT_BOT_TOKEN, default=DefaultBotProperties())
dp = Dispatcher()
router = Router()
dp.include_router(router)


class AuthFlow(StatesGroup):
    AWAITING_NEW_MERCHANT_ID = State()
    AWAITING_BROADCAST = State()
    AWAITING_PHONE = State()
    AWAITING_CODE = State()
    AWAITING_2FA = State()


EMOJIS = {'stop': '5395695537687123235', 'sad': '5366116089329646883',
    'warning': '5420323339723881652', 'halt': '5283283384418707920',
    'cross': '5800887979366944343', 'check': '5427009714745517609', 'party':
    '5461151367559121950', 'rocket': '5363945077850799577', 'money':
    '5350452584119279096', 'bank': '5264895611517300926', 'stats':
    '5431577498364158238', 'chart': '5431736674147114227', 'lock':
    '5472308992514464048', 'key': '5330115548900501467', 'shield':
    '5251203410396458957', 'id': '5422683699130933153', 'phone':
    '5465169893580086142', 'numbers': '5377624166436445368', 'green_circle':
    '5981066684977384749', 'red_circle': '5981335554225081686', 'trash':
    '5775903905498010383', 'globe': '5999317873623831250', 'email_send':
    '5406631276042002796', 'email_recv': '5253742260054409879', 'memo':
    '5373251851074415873', 'megaphone': '5424818078833715060', 'group':
    '5372926953978341366', 'person': '5373012449597335010', 'calendar':
    '5431897022456145283', 'plus': '5226945370684140473'}


def e(name: str, fallback: str) ->str:
    eid = EMOJIS.get(name)
    if not eid:
        return fallback
    return html.custom_emoji(fallback, custom_emoji_id=eid)


def is_admin(user_id: int) ->bool:
    if not settings.ADMIN_TELEGRAM_IDS:
        return False
    admin_ids = [int(x.strip()) for x in settings.ADMIN_TELEGRAM_IDS.split(
        ',') if x.strip().isdigit()]
    return user_id in admin_ids


async def _cleanup_state(user_id: int, state: FSMContext):
    await state.clear()
    state_data = user_states.pop(user_id, {})
    tc = state_data.get('temp_client')
    if tc and tc.is_connected():
        await tc.disconnect()


def get_admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text='Stats', callback_data=
        'admin_stats', icon_custom_emoji_id=EMOJIS['stats']),
        InlineKeyboardButton(text='Merchants', callback_data=
        'admin_merchants', icon_custom_emoji_id=EMOJIS['group']))
    builder.row(InlineKeyboardButton(text='Revenue', callback_data=
        'admin_revenue', icon_custom_emoji_id=EMOJIS['money']),
        InlineKeyboardButton(text='Recent', callback_data='admin_recent',
        icon_custom_emoji_id=EMOJIS['chart']))
    builder.row(InlineKeyboardButton(text='Errors', callback_data=
        'admin_errors', icon_custom_emoji_id=EMOJIS['warning']),
        InlineKeyboardButton(text='Broadcast', callback_data=
        'admin_broadcast', icon_custom_emoji_id=EMOJIS['megaphone']))
    builder.row(InlineKeyboardButton(text='View All Payments',
        callback_data='admin_payments_0', icon_custom_emoji_id=EMOJIS['stats'])
        )
    builder.row(InlineKeyboardButton(text='Add Merchant', callback_data=
        'admin_add_merchant', icon_custom_emoji_id=EMOJIS['plus']),
        InlineKeyboardButton(text='Close', callback_data='admin_close',
        icon_custom_emoji_id=EMOJIS['cross']))
    return builder.as_markup()


async def set_menus():
    user_cmds = [BotCommand(command='start', description=
        'Start the bot and link account'), BotCommand(command='credentials',
        description='View your Merchant ID and Secrets'), BotCommand(
        command='setcard', description='Set receiving card last 4 digits'),
        BotCommand(command='unsetcard', description=
        'Remove receiving card filter'), BotCommand(command='setwebhook',
        description='Set your webhook URL'), BotCommand(command=
        'disconnect', description='Disconnect your Telegram account')]
    await bot.set_my_commands(user_cmds, scope=BotCommandScopeDefault())
    if settings.ADMIN_TELEGRAM_IDS:
        admin_cmds = [BotCommand(command='start', description=
            'Open Admin Control Panel'), BotCommand(command='stats',
            description='View system statistics'), BotCommand(command=
            'merchants', description='List all connected merchants'),
            BotCommand(command='ban', description='Ban a merchant')]
        admin_ids = [int(x.strip()) for x in settings.ADMIN_TELEGRAM_IDS.
            split(',') if x.strip().isdigit()]
        for aid in admin_ids:
            try:
                await bot.set_my_commands(admin_cmds + user_cmds, scope=
                    BotCommandScopeChat(chat_id=aid))
            except Exception as ex:
                logger.warning(f'Could not set admin commands for {aid}: {ex}')


@router.message(Command('stats'))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"{e('stop', '⛔')} **Kechirasiz!** Ushbu amallarni bajarish uchun huquqingiz yo'q."
            ))
        return
    await send_stats(message)


async def send_stats(target: (Message | CallbackQuery)):
    db = SessionLocal()
    total_merchants = db.query(Merchant).count()
    connected_merchants = db.query(Merchant).filter(Merchant.is_connected ==
        True).count()
    total_intents = db.query(PaymentIntent).count()
    paid_intents = db.query(PaymentIntent).filter(PaymentIntent.status ==
        'PAID').count()
    total_payments = db.query(ProcessedPayment).count()
    db.close()
    text = f"""**{e('shield', '🛡️')} Admin Stats**

| Metric | Active / Paid | Total |
|:---|---:|---:|
| {e('group', '👥')} Merchants | {connected_merchants} | {total_merchants} |
| {e('memo', '📝')} Intents | {paid_intents} | {total_intents} |
| {e('money', '💰')} Payments | | {total_payments} |
"""
    markup = InlineKeyboardBuilder().row(InlineKeyboardButton(text='🔙 Back',
        callback_data='admin_back')).as_markup() if isinstance(target,
        CallbackQuery) else None
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(rich_message=InputRichMessage(
            markdown=text), reply_markup=markup)
    else:
        await target.answer_rich(rich_message=InputRichMessage(markdown=
            text), reply_markup=markup)


@router.message(Command('merchants'))
async def cmd_merchants(message: Message):
    if not is_admin(message.from_user.id):
        return
    await send_merchants(message)


async def send_merchants(target: (Message | CallbackQuery)):
    db = SessionLocal()
    merchants = db.query(Merchant).all()
    db.close()
    text = f"**{e('group', '👥')} Registered Merchants**\n\n"
    if not merchants:
        text += '*No merchants found.*'
    else:
        text += '~View Merchants~\n'
        text += '| Phone | ID | Status |\n'
        text += '|:---|:---|:---|\n'
        for m in merchants:
            status = e('green_circle', '🟢') if m.is_connected else e(
                'red_circle', '🔴')
            phone = m.phone_number if m.phone_number else 'Unknown Phone'
            text += (
                f"| {e('person', '🧑\\u200d💼')} {phone} | `{m.id}` | {status} |\n"
                )
        text += '~'
    markup = InlineKeyboardBuilder().row(InlineKeyboardButton(text='🔙 Back',
        callback_data='admin_back')).as_markup() if isinstance(target,
        CallbackQuery) else None
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(rich_message=InputRichMessage(
            markdown=text), reply_markup=markup)
    else:
        await target.answer_rich(rich_message=InputRichMessage(markdown=
            text), reply_markup=markup)


@router.message(Command('ban'))
async def cmd_ban(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(' ', 1)
    if len(parts) < 2:
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            'Please provide merchant ID.'))
        return
    merchant_id = parts[1].strip()
    db = SessionLocal()
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        db.close()
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"{e('sad', '😔')} **Afsuski!** Sizning profilingiz tizimdan topilmadi."
            ))
        return
    merchant.is_connected = False
    merchant.session_string = None
    db.commit()
    db.close()
    if _client_manager:
        await _client_manager.stop_client(merchant_id)
    await message.answer_rich(rich_message=InputRichMessage(markdown=
        f"{e('check', '✅')} **Ajoyib!** Merchant `{merchant_id}` muvaffaqiyatli ban qilindi va tizimdan uzildi."
        ))


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await _cleanup_state(message.from_user.id, state)
    if is_admin(message.from_user.id):
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"**{e('shield', '🛡️')} Admin Control Panel**"), reply_markup=
            get_admin_keyboard())
    else:
        db = SessionLocal()
        is_allowed = db.query(AllowedMerchant).filter(AllowedMerchant.
            telegram_id == str(message.from_user.id)).first()
        db.close()
        if not is_allowed:
            await message.answer_rich(rich_message=InputRichMessage(
                markdown=
                f"""{e('cross', '❌')} **Access Denied.**

You are not an authorized merchant. Please contact the administrator."""
                ))
            return
        await state.set_state(AuthFlow.AWAITING_PHONE)
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            """**👋 Welcome to Auto Payment Gateway!**

Send your Uzbek phone number to link your account:
Example: `+998901234567`"""
            ))


@router.message(Command('credentials'))
async def cmd_credentials(message: Message):
    db = SessionLocal()
    merchant_name = f'Merchant_{message.from_user.id}'
    merchant = db.query(Merchant).filter(Merchant.name == merchant_name).first(
        )
    db.close()
    if not merchant:
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"""{e('warning', '⚠️')} **Tizimga ulanmagansiz!**
Iltimos, /start orqali ulaning."""
            ))
        return
    await message.answer_rich(rich_message=InputRichMessage(markdown=
        f"""**{e('lock', '🔐')} Your Credentials**

**{e('id', '🆔')} Merchant ID:** `{merchant.id}`
**{e('shield', '🛡️')} Webhook Secret:** `{merchant.webhook_secret}`
**{e('globe', '🌐')} Webhook URL:** `{merchant.webhook_url or 'Not Set'}`

{e('warning', '⚠️')} *Note: API Key is mathematically hashed. Contact admin to reset.*"""
        ))


@router.message(Command('setcard'))
async def cmd_setcard(message: Message):
    parts = message.text.split(' ', 1)
    if len(parts) < 2:
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            'Usage: /setcard *4183'))
        return
    mask = parts[1].strip()
    mask_digits = mask.replace('*', '').strip()
    if not mask_digits.isdigit() or len(mask_digits) < 4:
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"""{e('warning', '⚠️')} **Noto'g'ri format!**
Iltimos, kartaning oxirgi 4 raqamini kiriting."""
            ))
        return
    db = SessionLocal()
    merchant_name = f'Merchant_{message.from_user.id}'
    merchant = db.query(Merchant).filter(Merchant.name == merchant_name).first(
        )
    if merchant:
        merchant.receiving_card_mask = mask
        db.commit()
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"""💳 **Muvaffaqiyatli saqlandi!**
Karta filtri: `{mask}` etib belgilandi."""
            ))
    else:
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"{e('sad', '😔')} **Afsuski!** Sizning profilingiz topilmadi."))
    db.close()


@router.message(Command('unsetcard'))
async def cmd_unsetcard(message: Message):
    if is_admin(message.from_user.id):
        return
    db = SessionLocal()
    merchant = db.query(Merchant).filter(Merchant.telegram_id == str(
        message.from_user.id)).first()
    if not merchant:
        db.close()
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"{e('sad', '😔')} **Siz tizimdan ro'yxatdan o'tmagansiz.**"))
        return
    merchant.receiving_card_mask = None
    db.commit()
    db.close()
    await message.answer_rich(rich_message=InputRichMessage(markdown=
        f"{e('trash', '🗑️')} **Karta filtri o'chirildi!**"))


@router.message(Command('setwebhook'))
async def cmd_setwebhook(message: Message):
    if is_admin(message.from_user.id):
        return
    parts = message.text.split(' ', 1)
    if len(parts) < 2:
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            'Usage: /setwebhook https://...'))
        return
    url = parts[1].strip()
    if not url.startswith('http://') and not url.startswith('https://'):
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"{e('globe', '🌐')} **Noto'g'ri Webhook manzili!**"))
        return
    db = SessionLocal()
    merchant = db.query(Merchant).filter(Merchant.telegram_id == str(
        message.from_user.id)).first()
    if not merchant:
        db.close()
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"{e('sad', '😔')} **Tizimga ulanmagansiz.**"))
        return
    merchant.webhook_url = url
    db.commit()
    db.close()
    await message.answer_rich(rich_message=InputRichMessage(markdown=
        f"""{e('rocket', '🚀')} **Webhook saqlandi:**
`{url}`"""))


@router.message(Command('disconnect'))
async def cmd_disconnect(message: Message):
    db = SessionLocal()
    merchant_name = f'Merchant_{message.from_user.id}'
    merchant = db.query(Merchant).filter(Merchant.name == merchant_name).first(
        )
    if merchant:
        merchant.is_connected = False
        merchant.session_string = None
        if _client_manager:
            await _client_manager.stop_client(merchant.id)
        db.commit()
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            """🔌 **Sessiya to'xtatildi!**
Bot endi SMS xabarlaringizni o'qimaydi."""
            ))
    else:
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"{e('warning', '⚠️')} **Siz tizimga ulanmagansiz!**"))
    db.close()


@router.message(AuthFlow.AWAITING_PHONE)
async def process_phone(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.startswith('+') or len(text) < 10:
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"""{e('phone', '📱')} **Telefon raqam noto'g'ri!**
Format: `+998901234567`"""
            ))
        return
    await message.answer_rich(rich_message=InputRichMessage(markdown=
        f"{e('email_send', '📨')} **Tasdiqlash kodi yuborilmoqda...**"))
    temp_client = TelegramClient(StringSession(), API_ID, API_HASH)
    await temp_client.connect()
    try:
        sent = await temp_client.send_code_request(text)
        user_states[message.from_user.id] = {'temp_client': temp_client}
        await state.update_data(phone=text, phone_code_hash=sent.
            phone_code_hash)
        await state.set_state(AuthFlow.AWAITING_CODE)
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"""{e('email_recv', '📩')} Code sent! Reply with:
`CODE 12345`"""))
    except Exception as ex:
        logger.error(f'send_code_request failed: {ex}')
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"{e('cross', '❌')} Failed: {ex}"))
        await _cleanup_state(message.from_user.id, state)


@router.message(AuthFlow.AWAITING_CODE)
async def process_code(message: Message, state: FSMContext):
    text = message.text.strip().upper()
    if not text.startswith('CODE '):
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"""{e('warning', '⚠️')} **Format:**
`CODE 12345`"""))
        return
    code = text.split(' ', 1)[1].strip()
    data = await state.get_data()
    phone = data['phone']
    phone_code_hash = data['phone_code_hash']
    udata = user_states.get(message.from_user.id, {})
    temp_client: TelegramClient = udata.get('temp_client')
    if not temp_client:
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"{e('cross', '❌')} Xatolik: Sessiya topilmadi. /start"))
        await state.clear()
        return
    try:
        await temp_client.sign_in(phone=phone, code=code, phone_code_hash=
            phone_code_hash)
        await _finish_login(message, temp_client, phone, state)
    except SessionPasswordNeededError:
        await state.set_state(AuthFlow.AWAITING_2FA)
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"{e('lock', '🔐')} Ikki bosqichli parol o'rnatilgan. Parolni yuboring:"
            ))
    except Exception as ex:
        logger.error(f'sign_in failed: {ex}')
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"{e('cross', '❌')} **Ulanishda xatolik:** {ex}"))
        await _cleanup_state(message.from_user.id, state)


@router.message(AuthFlow.AWAITING_2FA)
async def process_2fa(message: Message, state: FSMContext):
    password = message.text.strip()
    data = await state.get_data()
    phone = data['phone']
    udata = user_states.get(message.from_user.id, {})
    temp_client: TelegramClient = udata.get('temp_client')
    if not temp_client:
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"{e('cross', '❌')} Xatolik: Sessiya topilmadi. /start"))
        await state.clear()
        return
    try:
        await temp_client.sign_in(password=password)
        await _finish_login(message, temp_client, phone, state)
    except Exception as ex:
        logger.error(f'sign_in 2fa failed: {ex}')
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"{e('cross', '❌')} **Xato:** {ex}"))
        await _cleanup_state(message.from_user.id, state)


async def _finish_login(message: Message, temp_client: TelegramClient,
    phone: str, state: FSMContext):
    session_string = temp_client.session.save()
    encrypted_session = encrypt_session(session_string)
    merchant_name = f'Merchant_{message.from_user.id}'
    telegram_id = str(message.from_user.id)
    db = SessionLocal()
    merchant = db.query(Merchant).filter(Merchant.name == merchant_name).first(
        )
    is_new = False
    raw_api_key = ''
    if not merchant:
        raw_api_key, hashed_key = generate_api_key()
        webhook_secret = generate_webhook_secret()
        merchant = Merchant(name=merchant_name, telegram_id=telegram_id,
            api_key_hash=hashed_key, webhook_secret=webhook_secret,
            webhook_url='')
        db.add(merchant)
        is_new = True
    merchant.encrypted_session = encrypted_session
    merchant.phone_number = phone
    merchant.is_connected = True
    db.commit()
    merchant_id = merchant.id
    raw_key_to_show = raw_api_key if is_new else '********'
    db.close()
    await temp_client.disconnect()
    await state.clear()
    user_states.pop(message.from_user.id, None)
    if _client_manager:
        await _client_manager.start_client(merchant_id, session_string)
    msg = f"{e('party', '🎉')} **Ajoyib! Hisobingiz ulandi.**\n\n"
    msg += f"{e('id', '🆔')} **Merchant ID:** `{merchant_id}`\n"
    if is_new:
        msg += f"{e('key', '🔑')} **API Kalit:** `{raw_key_to_show}`\n\n"
        msg += (
            f"{e('warning', '⚠️')} *API Kalitni hoziroq saqlab oling. Boshqa ko'rsatilmaydi!*\n"
            )
    await message.answer_rich(rich_message=InputRichMessage(markdown=msg))


@router.callback_query(F.data == 'admin_stats')
async def cb_stats(query: CallbackQuery):
    await send_stats(query)


@router.callback_query(F.data == 'admin_merchants')
async def cb_merchants(query: CallbackQuery):
    await send_merchants(query)


@router.callback_query(F.data == 'admin_revenue')
async def cb_revenue(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return
    db = SessionLocal()
    revenue_tiyins = db.query(func.sum(PaymentIntent.expected_amount_tiyins)
        ).filter(PaymentIntent.status == 'PAID').scalar() or 0
    total_revenue = revenue_tiyins / 100
    db.close()
    text = f"""**{e('money', '💰')} Revenue Tracker**

| Metric | Value |
|:---|---:|
| Total Volume | **{total_revenue:,.0f}** UZS |

*(Sum of all successfully paid intents)*"""
    markup = InlineKeyboardBuilder().row(InlineKeyboardButton(text='🔙 Back',
        callback_data='admin_back')).as_markup()
    await query.message.edit_text(rich_message=InputRichMessage(markdown=
        text), reply_markup=markup)


@router.callback_query(F.data == 'admin_recent')
async def cb_recent(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return
    db = SessionLocal()
    recent = db.query(ProcessedPayment).order_by(ProcessedPayment.
        date_received.desc()).limit(5).all()
    db.close()
    text = f"**{e('chart', '📈')} Recent Transactions**\n\n"
    if not recent:
        text += '*No transactions yet.*'
    else:
        text += '| ID | Source | Amount (UZS) | Date | Status |\n'
        text += '|:---|:---|---:|:---|:---|\n'
        for r in recent:
            amount = r.amount_tiyins / 100
            source_emoji = '💳' if r.source in ('PAYME', 'CLICK') else e('bank',
                '🏦')
            text += f"""| `#{r.id[:6]}` | {source_emoji} {r.source} | **{amount:,.0f}** | `{r.date_received.strftime('%Y-%m-%d %H:%M')}` | {e('check', '✅')} **{r.status}** |
"""
    markup = InlineKeyboardBuilder().row(InlineKeyboardButton(text='🔙 Back',
        callback_data='admin_back')).as_markup()
    await query.message.edit_text(rich_message=InputRichMessage(markdown=
        text), reply_markup=markup)


@router.callback_query(F.data == 'admin_errors')
async def cb_errors(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return
    db = SessionLocal()
    errors = db.query(UnparsedMessage).filter(UnparsedMessage.is_resolved ==
        False).order_by(UnparsedMessage.date_received.desc()).limit(5).all()
    db.close()
    text = f"**{e('warning', '⚠️')} Recent Unparsed Messages (DLQ)**\n\n"
    if not errors:
        text += f"{e('check', '✅')} *All systems normal.*"
    else:
        text += '~View Errors~\n'
        text += '| Error | Date | Text |\n'
        text += '|:---|:---|:---|\n'
        for er in errors:
            text += f"""| {er.error_reason} | {er.date_received.strftime('%Y-%m-%d %H:%M')} | `{er.raw_text[:50]}...` |
"""
        text += '~'
    markup = InlineKeyboardBuilder().row(InlineKeyboardButton(text='🔙 Back',
        callback_data='admin_back')).as_markup()
    await query.message.edit_text(rich_message=InputRichMessage(markdown=
        text), reply_markup=markup)


@router.callback_query(F.data == 'admin_broadcast')
async def cb_broadcast(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    await state.set_state(AuthFlow.AWAITING_BROADCAST)
    markup = InlineKeyboardBuilder().row(InlineKeyboardButton(text=
        '🔙 Cancel', callback_data='admin_back')).as_markup()
    await query.message.edit_text(rich_message=InputRichMessage(markdown=
        f"""**{e('megaphone', '📢')} Broadcast Mode Activated**

Send the message you want to broadcast."""
        ), reply_markup=markup)


@router.message(AuthFlow.AWAITING_BROADCAST)
async def process_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    if not text:
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"{e('memo', '📝')} **Xabar bo'sh!**"))
        return
    await message.answer_rich(rich_message=InputRichMessage(markdown=
        f"{e('rocket', '🚀')} **Barcha merchantlarga yuborilmoqda...**"))
    db = SessionLocal()
    merchants = db.query(Merchant).all()
    db.close()
    success = 0
    for m in merchants:
        if m.name.startswith('Merchant_'):
            m_id = int(m.name.split('_')[1])
            try:
                await bot.send_rich_message(m_id,
                    f"""{e('megaphone', '📢')} **Announcement from Admin**

{text}"""
                    )
                success += 1
            except Exception as ex:
                logger.error(f'Broadcast failed to {m_id}: {ex}')
    await state.clear()
    await message.answer_rich(rich_message=InputRichMessage(markdown=
        f"{e('check', '✅')} **E'lon yuborildi!** Jami {success} ta."))


@router.callback_query(F.data.startswith('admin_payments_'))
async def cb_payments(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        return
    page = int(query.data.split('_')[2])
    per_page = 5
    offset = page * per_page
    db = SessionLocal()
    total_count = db.query(ProcessedPayment).count()
    payments = db.query(ProcessedPayment, Merchant).join(Merchant, 
        ProcessedPayment.merchant_id == Merchant.id).order_by(ProcessedPayment
        .date_received.desc()).offset(offset).limit(per_page).all()
    db.close()
    text = f"**{e('stats', '📊')} Payments Database (Page {page + 1})**\n\n"
    if total_count == 0:
        text += '*No payments found.*'
    else:
        text += '| ID | Source | Merchant | Amount | Date | Status |\n'
        text += '|:---|:---|:---|---:|:---|:---|\n'
        for p, m in payments:
            amt = p.amount_tiyins / 100
            source_emoji = '💳' if p.source in ('PAYME', 'CLICK') else e('bank',
                '🏦')
            text += f"""| `#{p.id[:6]}` | {source_emoji} {p.source} | `{m.phone_number or 'Unknown'}` | **{amt:,.0f}** | `{p.date_received.strftime('%Y-%m-%d %H:%M:%S')}` | {e('check', '✅')} **{p.status}** |
"""
        text += f'\n*Total records: {total_count}*'
    builder = InlineKeyboardBuilder()
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text='Prev', callback_data=
            f'admin_payments_{page - 1}'))
    if offset + per_page < total_count:
        nav.append(InlineKeyboardButton(text='Next', callback_data=
            f'admin_payments_{page + 1}'))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text='🔙 Back', callback_data='admin_back')
        )
    await query.message.edit_text(rich_message=InputRichMessage(markdown=
        text), reply_markup=builder.as_markup())


@router.callback_query(F.data == 'admin_add_merchant')
async def cb_add_merchant(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    await state.set_state(AuthFlow.AWAITING_NEW_MERCHANT_ID)
    markup = InlineKeyboardBuilder().row(InlineKeyboardButton(text=
        '🔙 Cancel', callback_data='admin_back')).as_markup()
    await query.message.edit_text(rich_message=InputRichMessage(markdown=
        f"""**{e('plus', '➕')} Add a New Merchant**

Please reply with the Telegram User ID of the new merchant."""
        ), reply_markup=markup)


@router.message(AuthFlow.AWAITING_NEW_MERCHANT_ID)
async def process_new_merchant(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    if not text.isdigit():
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"{e('numbers', '🔢')} **Noto'g'ri Telegram ID!**"))
        return
    db = SessionLocal()
    existing = db.query(AllowedMerchant).filter(AllowedMerchant.telegram_id ==
        text).first()
    if existing:
        db.close()
        await message.answer_rich(rich_message=InputRichMessage(markdown=
            f"{e('check', '✅')} **Oldin qo'shilgan!**"))
        await state.clear()
        return
    db.add(AllowedMerchant(telegram_id=text))
    db.commit()
    db.close()
    await state.clear()
    await message.answer_rich(rich_message=InputRichMessage(markdown=
        f"{e('party', '🎉')} **Merchant qo'shildi!** `{text}` ulanishi mumkin.")
        )


@router.callback_query(F.data == 'admin_back')
async def cb_admin_back(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    await state.clear()
    await query.message.edit_text(rich_message=InputRichMessage(markdown=
        f"**{e('shield', '🛡️')} Admin Control Panel**"), reply_markup=
        get_admin_keyboard())


@router.callback_query(F.data == 'admin_close')
async def cb_admin_close(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        return
    await state.clear()
    await query.message.delete()
