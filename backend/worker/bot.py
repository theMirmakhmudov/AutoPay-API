import asyncio
import logging
from uuid import uuid4
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from core.database import SessionLocal
from core.config import settings
from core.encryption import encrypt_session, generate_api_key, generate_webhook_secret
from models.payment import Merchant, PaymentIntent, ProcessedPayment
from services.payment_service import PaymentService
from schemas.payload import CreatePaymentRequest

logger = logging.getLogger(__name__)

API_ID = settings.TELEGRAM_API_ID
API_HASH = settings.TELEGRAM_API_HASH
BOT_TOKEN = settings.MANAGEMENT_BOT_TOKEN

management_bot = TelegramClient('management_bot_session', API_ID, API_HASH)

user_states = {}
_client_manager = None

def set_client_manager(manager):
    global _client_manager
    _client_manager = manager

async def _cleanup_state(user_id: int):
    state = user_states.pop(user_id, {})
    tc = state.get("temp_client")
    if tc and tc.is_connected():
        await tc.disconnect()

def is_admin(user_id: int) -> bool:
    if user_id == 6716993468:
        return True
    if not settings.ADMIN_TELEGRAM_IDS:
        return False
    admin_ids = [int(x.strip()) for x in settings.ADMIN_TELEGRAM_IDS.split(",") if x.strip().isdigit()]
    return user_id in admin_ids

# ── Admin Commands ─────────────────────────────────────────────────────────

@management_bot.on(events.NewMessage(pattern='/stats'))
async def stats_handler(event):
    if not is_admin(event.sender_id):
        await event.respond("❌ Access denied.")
        return
        
    db = SessionLocal()
    total_merchants = db.query(Merchant).count()
    connected_merchants = db.query(Merchant).filter(Merchant.is_connected == True).count()
    
    total_intents = db.query(PaymentIntent).count()
    paid_intents = db.query(PaymentIntent).filter(PaymentIntent.status == "PAID").count()
    
    total_payments = db.query(ProcessedPayment).count()
    db.close()
    
    await event.respond(
        f"<b>🛡️ Admin Stats</b>\n\n"
        f"<b>👥 Merchants:</b> {connected_merchants} active / {total_merchants} total\n"
        f"<b>📝 Intents:</b> {paid_intents} paid / {total_intents} total\n"
        f"<b>💰 Processed Payments:</b> {total_payments}\n",
        parse_mode='html'
    )

@management_bot.on(events.NewMessage(pattern='/merchants'))
async def merchants_handler(event):
    if not is_admin(event.sender_id):
        await event.respond("❌ Access denied.")
        return
        
    db = SessionLocal()
    merchants = db.query(Merchant).all()
    db.close()
    
    if not merchants:
        await event.respond("No merchants found.")
        return
        
    text = "<b>👥 Registered Merchants</b>\n\n"
    for m in merchants:
        status = "🟢" if m.is_connected else "🔴"
        text += f"{status} <code>{m.id}</code>\n<b>Phone:</b> {m.phone_number}\n\n"
        
    await event.respond(text[:4000], parse_mode='html')

@management_bot.on(events.NewMessage(pattern=r'/ban (.+)'))
async def ban_handler(event):
    if not is_admin(event.sender_id):
        await event.respond("❌ Access denied.")
        return
        
    merchant_id = event.pattern_match.group(1).strip()
    db = SessionLocal()
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    
    if not merchant:
        db.close()
        await event.respond("❌ Merchant not found.")
        return
        
    merchant.is_connected = False
    merchant.session_string = None
    db.commit()
    db.close()
    
    if _client_manager:
        await _client_manager.stop_client(merchant_id)
        
    await event.respond(f"✅ Merchant <code>{merchant_id}</code> banned and disconnected.", parse_mode='html')


@management_bot.on(events.NewMessage(pattern='/admin'))
async def admin_panel_handler(event):
    if not is_admin(event.sender_id):
        await event.respond("❌ Access denied.")
        return
    
    await event.respond(
        "<b>🛡️ Admin Panel</b>",
        parse_mode='html',
        buttons=[
            [Button.inline("📊 Stats", b"admin_stats"), Button.inline("👥 Merchants", b"admin_merchants")],
            [Button.inline("❌ Close", b"admin_close")]
        ]
    )

@management_bot.on(events.CallbackQuery(pattern=b'admin_stats'))
async def callback_stats(event):
    if not is_admin(event.sender_id):
        return
    db = SessionLocal()
    total_merchants = db.query(Merchant).count()
    connected_merchants = db.query(Merchant).filter(Merchant.is_connected == True).count()
    total_intents = db.query(PaymentIntent).count()
    paid_intents = db.query(PaymentIntent).filter(PaymentIntent.status == "PAID").count()
    total_payments = db.query(ProcessedPayment).count()
    db.close()
    await event.edit(
        f"<b>🛡️ Admin Stats</b>\n\n"
        f"<b>👥 Merchants:</b> {connected_merchants} active / {total_merchants} total\n"
        f"<b>📝 Intents:</b> {paid_intents} paid / {total_intents} total\n"
        f"<b>💰 Processed Payments:</b> {total_payments}\n",
        parse_mode='html',
        buttons=[[Button.inline("⬅️ Back", b"admin_back")]]
    )

@management_bot.on(events.CallbackQuery(pattern=b'admin_merchants'))
async def callback_merchants(event):
    if not is_admin(event.sender_id):
        return
    db = SessionLocal()
    merchants = db.query(Merchant).all()
    db.close()
    
    text = "<b>👥 Registered Merchants</b>\n\n"
    if not merchants:
        text += "No merchants found."
    else:
        for m in merchants:
            status = "🟢" if m.is_connected else "🔴"
            text += f"{status} <code>{m.id}</code>\n<b>Phone:</b> {m.phone_number}\n\n"
            
    await event.edit(text[:4000], parse_mode='html', buttons=[[Button.inline("⬅️ Back", b"admin_back")]])

@management_bot.on(events.CallbackQuery(pattern=b'admin_back'))
async def callback_back(event):
    if not is_admin(event.sender_id):
        return
    await event.edit(
        "<b>🛡️ Admin Panel</b>",
        parse_mode='html',
        buttons=[
            [Button.inline("📊 Stats", b"admin_stats"), Button.inline("👥 Merchants", b"admin_merchants")],
            [Button.inline("❌ Close", b"admin_close")]
        ]
    )

@management_bot.on(events.CallbackQuery(pattern=b'admin_close'))
async def callback_close(event):
    if not is_admin(event.sender_id):
        return
    await event.delete()


# ── Merchant Commands ──────────────────────────────────────────────────────

@management_bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await _cleanup_state(event.sender_id)
    user_states[event.sender_id] = {"state": "AWAITING_PHONE"}
    
    admin_text = "\n\n<b>🛡️ Admin Commands:</b>\n<code>/stats</code>, <code>/merchants</code>, <code>/ban &lt;id&gt;</code>" if is_admin(event.sender_id) else ""
    
    await event.respond(
        f"<b>👋 Welcome to Auto Payment Gateway!</b>\n\n"
        f"Send your Uzbek phone number to link your account:\n"
        f"Example: <code>+998901234567</code>{admin_text}",
        parse_mode='html'
    )

@management_bot.on(events.NewMessage(pattern='/credentials'))
async def credentials_handler(event):
    db = SessionLocal()
    merchant_name = f"Merchant_{event.sender_id}"
    merchant = db.query(Merchant).filter(Merchant.name == merchant_name).first()
    db.close()
    
    if not merchant:
        await event.respond("❌ You are not connected. Send /start")
        return
        
    await event.respond(
        f"<b>🔐 Your Credentials</b>\n\n"
        f"<b>🆔 Merchant ID:</b> <code>{merchant.id}</code>\n"
        f"<b>🛡️ Webhook Secret:</b> <code>{merchant.webhook_secret}</code>\n"
        f"<b>🌐 Webhook URL:</b> <code>{merchant.webhook_url or 'Not Set'}</code>\n\n"
        f"⚠️ <i>Note: For security reasons, your API Key is mathematically hashed. We cannot show it to you. If you lost it, contact an admin to reset it.</i>",
        parse_mode='html'
    )

@management_bot.on(events.NewMessage(pattern='/status'))
async def status_handler(event):
    db = SessionLocal()
    merchant_name = f"Merchant_{event.sender_id}"
    merchant = db.query(Merchant).filter(Merchant.name == merchant_name).first()
    db.close()
    
    if merchant and merchant.is_connected:
        await event.respond("✅ Your account is connected and actively listening for payments.\nUse /create <amount> to generate a payment intent.")
    else:
        await event.respond("ℹ️ Your account is not connected. Use /start to connect a new account.")

@management_bot.on(events.NewMessage(pattern=r'/create (\d+)'))
async def create_payment_handler(event):
    amount_str = event.pattern_match.group(1).strip()
    base_amount = float(amount_str)
    
    db = SessionLocal()
    merchant_name = f"Merchant_{event.sender_id}"
    merchant = db.query(Merchant).filter(Merchant.name == merchant_name).first()
    
    if not merchant or not merchant.is_connected:
        db.close()
        await event.respond("❌ You must be connected to create a payment. Send /start")
        return
        
    service = PaymentService(db)
    req = CreatePaymentRequest(base_amount=base_amount)
    try:
        intent = service.create_payment_intent(merchant.id, req)
        display_amount = f"{intent.expected_amount / 100:,.2f} UZS"
        
        await event.respond(
            f"<b>💰 Payment Intent Created</b>\n\n"
            f"Forward this to your customer:\n"
            f"<code>Please pay exactly {display_amount} to card 8600...</code>\n\n"
            f"Wait for the confirmation message here when paid.",
            parse_mode='html'
        )
    except Exception as e:
        logger.error(f"Failed to create intent: {e}")
        await event.respond("❌ Failed to create payment intent due to high collision volume. Try again in a minute.")
    finally:
        db.close()

@management_bot.on(events.NewMessage(pattern=r'/setwebhook (.+)'))
async def setwebhook_handler(event):
    url = event.pattern_match.group(1).strip()
    if not url.startswith("https://"):
        await event.respond("❌ Webhook URL must start with https://")
        return
    db = SessionLocal()
    merchant_name = f"Merchant_{event.sender_id}"
    merchant = db.query(Merchant).filter(Merchant.name == merchant_name).first()
    if merchant:
        merchant.webhook_url = url
        db.commit()
        await event.respond(f"✅ Webhook URL set to: <code>{url}</code>", parse_mode='html')
    else:
        await event.respond("❌ Merchant not found.")
    db.close()

@management_bot.on(events.NewMessage(pattern='/disconnect'))
async def disconnect_handler(event):
    db = SessionLocal()
    merchant_name = f"Merchant_{event.sender_id}"
    merchant = db.query(Merchant).filter(Merchant.name == merchant_name).first()
    if merchant:
        merchant.is_connected = False
        merchant.session_string = None
        if _client_manager:
            await _client_manager.stop_client(merchant.id)
        db.commit()
        await event.respond("✅ Your Telegram account has been disconnected from the platform.")
    else:
        await event.respond("❌ You are not connected.")
    db.close()

# ── Authentication State Machine ───────────────────────────────────────────

@management_bot.on(events.NewMessage(func=lambda e: e.text and not e.text.startswith('/')))
async def message_handler(event):
    user_id = event.sender_id
    text = event.text.strip()

    if user_id not in user_states:
        # Ignore non-commands if not in auth flow
        return

    state_data = user_states[user_id]
    current_state = state_data.get("state")

    if current_state == "AWAITING_PHONE":
        if not text.startswith("+") or len(text) < 10:
            await event.respond("Please send a valid phone number (e.g. <code>+998901234567</code>)", parse_mode='html')
            return

        await event.respond("⏳ Sending Telegram login code...")
        temp_client = TelegramClient(StringSession(), API_ID, API_HASH)
        await temp_client.connect()

        try:
            sent = await temp_client.send_code_request(text)
            state_data.update({
                "phone": text,
                "temp_client": temp_client,
                "phone_code_hash": sent.phone_code_hash,
                "state": "AWAITING_CODE"
            })
            await event.respond(
                "📩 Code sent! Reply with:\n<code>CODE 12345</code>\n\n"
                "(Prefix with CODE so Telegram doesn't intercept it)",
                parse_mode='html'
            )
        except Exception as e:
            logger.error(f"send_code_request failed: {e}")
            await event.respond(f"❌ Failed: {e}")
            await _cleanup_state(user_id)

    elif current_state == "AWAITING_CODE":
        if not text.upper().startswith("CODE "):
            await event.respond("Please reply with the code in format: <code>CODE 12345</code>", parse_mode='html')
            return

        code = text.split(" ", 1)[1].strip()
        temp_client = state_data["temp_client"]
        phone = state_data["phone"]
        phone_code_hash = state_data["phone_code_hash"]

        try:
            await temp_client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            await _finish_login(event, temp_client, phone, user_id)

        except SessionPasswordNeededError:
            state_data["state"] = "AWAITING_2FA"
            await event.respond(
                "🔐 Your account has <b>Two-Step Verification</b> enabled.\n"
                "Please send your Telegram password now:",
                parse_mode='html'
            )
        except Exception as e:
            logger.error(f"sign_in failed: {e}")
            await event.respond(f"❌ Verification failed: {e}\nSend /start to try again.")
            await _cleanup_state(user_id)

    elif current_state == "AWAITING_2FA":
        temp_client = state_data["temp_client"]
        phone = state_data["phone"]
        try:
            await temp_client.sign_in(password=text)
            await _finish_login(event, temp_client, phone, user_id)
        except Exception as e:
            logger.error(f"2FA sign_in failed: {e}")
            await event.respond(f"❌ Wrong password. Send /start to try again.")
            await _cleanup_state(user_id)


async def _finish_login(event, temp_client: TelegramClient, phone: str, user_id: int):
    session_string = temp_client.session.save()
    await temp_client.disconnect()

    db = SessionLocal()
    raw_api_key, api_key_hash = generate_api_key()
    webhook_secret = generate_webhook_secret()

    new_merchant = Merchant(
        id=str(uuid4()),
        name=f"Merchant_{user_id}",
        api_key_hash=api_key_hash,
        phone_number=phone,
        encrypted_session=encrypt_session(session_string),
        is_connected=True,
        webhook_secret=webhook_secret
    )
    db.add(new_merchant)
    db.commit()
    db.refresh(new_merchant)
    db.close()

    user_states.pop(user_id, None)

    if _client_manager:
        await _client_manager.start_client(new_merchant)
        logger.info(f"Hot-loaded userbot for new merchant {new_merchant.id}")

    await event.respond(
        f"<b>✅ Account linked!</b>\n\n"
        f"<b>🆔 Merchant ID:</b> <code>{new_merchant.id}</code>\n"
        f"<b>🔑 API Key:</b> <code>{raw_api_key}</code>\n"
        f"<b>🛡️ Webhook Secret:</b> <code>{webhook_secret}</code>\n\n"
        f"⚠️ <b>Save these secrets now — they will never be shown again!</b>\n"
        f"You can now use <code>/create 35000</code> to test a payment.",
        parse_mode='html'
    )
