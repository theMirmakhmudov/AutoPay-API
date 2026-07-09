import asyncio
import logging
import csv
import os
from uuid import uuid4
from sqlalchemy import func
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from core.database import SessionLocal
from core.config import settings
from core.encryption import encrypt_session, generate_api_key, generate_webhook_secret
from models.payment import Merchant, PaymentIntent, ProcessedPayment, UnparsedMessage
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
    table = f"{'Metric':<15} | {'Value':<12}\n"
    table += "-" * 30 + "\n"
    table += f"{'Merchants':<15} | {f'{connected_merchants}/{total_merchants}':<12}\n"
    table += f"{'Invoices(Paid)':<15} | {f'{paid_intents}/{total_intents}':<12}\n"
    table += f"{'Total Processed':<15} | {total_payments:<12}\n"
    
    await event.respond(
        f"<b>🛡️ Admin Stats</b>\n\n<pre>{table}</pre>",
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


# ── Merchant Commands ──────────────────────────────────────────────────────

@management_bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await _cleanup_state(event.sender_id)
    
    if is_admin(event.sender_id):
        # Dynamically inject the Admin-only commands menu for this specific admin
        try:
            from telethon.tl.functions.bots import SetBotCommandsRequest
            from telethon.tl.types import BotCommand, BotCommandScopePeer
            user_cmds = [
                BotCommand(command="start", description="Start the bot and link account"),
                BotCommand(command="credentials", description="View your Merchant ID and Secrets"),
                BotCommand(command="status", description="Check connection status"),
                BotCommand(command="create", description="Generate a payment intent"),
                BotCommand(command="setwebhook", description="Set webhook URL"),
                BotCommand(command="disconnect", description="Disconnect your Telegram account")
            ]
            admin_cmds = [
                BotCommand(command="start", description="Open Admin Control Panel"),
                BotCommand(command="stats", description="View system statistics"),
                BotCommand(command="merchants", description="List all connected merchants"),
                BotCommand(command="ban", description="Ban a merchant")
            ]
            await management_bot(SetBotCommandsRequest(
                scope=BotCommandScopePeer(event.input_sender),
                lang_code='',
                commands=admin_cmds + user_cmds
            ))
        except Exception as e:
            logger.error(f"Failed to set admin commands menu: {e}")
            
        await event.respond(
            "<b>🛡️ Admin Control Panel</b>",
            parse_mode='html',
            buttons=[
                [Button.inline("📊 Stats", b"admin_stats"), Button.inline("👥 Merchants", b"admin_merchants")],
                [Button.inline("💰 Revenue", b"admin_revenue"), Button.inline("📈 Recent", b"admin_recent")],
                [Button.inline("⚠️ Errors", b"admin_errors"), Button.inline("📢 Broadcast", b"admin_broadcast")],
                [Button.inline("📊 View All Payments", b"admin_payments_0")],
                [Button.inline("❌ Close", b"admin_close")]
            ]
        )
    else:
        user_states[event.sender_id] = {"state": "AWAITING_PHONE"}
        await event.respond(
            f"<b>👋 Welcome to Auto Payment Gateway!</b>\n\n"
            f"Send your Uzbek phone number to link your account:\n"
            f"Example: <code>+998901234567</code>",
            parse_mode='html'
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
    table = f"{'Metric':<15} | {'Value':<12}\n"
    table += "-" * 30 + "\n"
    table += f"{'Merchants':<15} | {f'{connected_merchants}/{total_merchants}':<12}\n"
    table += f"{'Invoices(Paid)':<15} | {f'{paid_intents}/{total_intents}':<12}\n"
    table += f"{'Total Processed':<15} | {total_payments:<12}\n"
    
    await event.edit(
        f"<b>🛡️ Admin Stats</b>\n\n<pre>{table}</pre>",
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

@management_bot.on(events.CallbackQuery(pattern=b'admin_revenue'))
async def callback_revenue(event):
    if not is_admin(event.sender_id):
        return
    db = SessionLocal()
    revenue_tiyins = db.query(func.sum(PaymentIntent.expected_amount_tiyins)).filter(PaymentIntent.status == "PAID").scalar() or 0
    total_revenue = revenue_tiyins / 100
    db.close()
    
    await event.edit(
        f"<b>💰 Revenue Tracker</b>\n\n"
        f"<b>Total Volume Processed:</b> {total_revenue:,.2f} UZS\n\n"
        f"<i>(This is the sum of all successfully paid payment intents)</i>",
        parse_mode='html',
        buttons=[[Button.inline("⬅️ Back", b"admin_back")]]
    )

@management_bot.on(events.CallbackQuery(pattern=b'admin_recent'))
async def callback_recent(event):
    if not is_admin(event.sender_id):
        return
    db = SessionLocal()
    recent = db.query(ProcessedPayment).order_by(ProcessedPayment.date_received.desc()).limit(5).all()
    db.close()
    
    text = "<b>📈 Recent Transactions</b>\n\n"
    if not recent:
        text += "No transactions yet."
    for r in recent:
        amount = r.amount_tiyins / 100
        text += f"▪️ <b>{amount:,.2f} UZS</b> via {r.source}\n   Date: {r.date_received.strftime('%Y-%m-%d %H:%M')}\n   Status: {r.status}\n\n"
        
    await event.edit(text[:4000], parse_mode='html', buttons=[[Button.inline("⬅️ Back", b"admin_back")]])

@management_bot.on(events.CallbackQuery(pattern=b'admin_errors'))
async def callback_errors(event):
    if not is_admin(event.sender_id):
        return
    db = SessionLocal()
    errors = db.query(UnparsedMessage).filter(UnparsedMessage.is_resolved == False).order_by(UnparsedMessage.date_received.desc()).limit(5).all()
    db.close()
    
    text = "<b>⚠️ Recent Unparsed Messages (Dead Letter Queue)</b>\n\n"
    if not errors:
        text += "✅ All systems normal. No recent parsing errors."
    for e in errors:
        text += f"▪️ <b>Error:</b> {e.error_reason}\n   <b>Date:</b> {e.date_received.strftime('%Y-%m-%d %H:%M')}\n   <code>{e.raw_text[:50]}...</code>\n\n"
        
    await event.edit(text[:4000], parse_mode='html', buttons=[[Button.inline("⬅️ Back", b"admin_back")]])

@management_bot.on(events.CallbackQuery(pattern=b'admin_broadcast'))
async def callback_broadcast(event):
    if not is_admin(event.sender_id):
        return
    user_states[event.sender_id] = {"state": "AWAITING_BROADCAST"}
    await event.edit(
        "<b>📢 Broadcast Mode Activated</b>\n\n"
        "Send the message you want to broadcast to ALL merchants now. (Or click Back to cancel)",
        parse_mode='html',
        buttons=[[Button.inline("⬅️ Cancel", b"admin_back")]]
    )

@management_bot.on(events.CallbackQuery(pattern=br'admin_payments_(\d+)'))
async def callback_payments_table(event):
    if not is_admin(event.sender_id):
        return
    page = int(event.pattern_match.group(1))
    per_page = 15
    offset = page * per_page
    
    db = SessionLocal()
    total_count = db.query(ProcessedPayment).count()
    payments = db.query(ProcessedPayment, Merchant).join(Merchant, ProcessedPayment.merchant_id == Merchant.id).order_by(ProcessedPayment.date_received.desc()).offset(offset).limit(per_page).all()
    db.close()
    
    table = f"{'Date':<5} | {'Phone':<9} | {'Amount':<7} | {'Src':<4}\n"
    table += "-" * 33 + "\n"
    for p, m in payments:
        date_str = p.date_received.strftime("%m-%d")
        phone = m.phone_number[-9:] if (m.phone_number and len(m.phone_number) >= 9) else "Unknown  "
        amt = p.amount_tiyins / 100
        if amt >= 1000000:
            amt_str = f"{amt/1000000:.1f}M"
        elif amt >= 1000:
            amt_str = f"{amt/1000:.0f}k"
        else:
            amt_str = str(int(amt))
        src = p.source[:4] if p.source else "UNK"
        
        table += f"{date_str:<5} | {phone:<9} | {amt_str:<7} | {src:<4}\n"
        
    text = f"<b>📊 Payments Database (Page {page+1})</b>\n\n"
    if total_count == 0:
        text += "<i>No payments found.</i>\n"
    else:
        text += f"<pre>{table}</pre>\n"
    text += f"<i>Total records: {total_count}</i>"
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(Button.inline("⬅️ Prev", f"admin_payments_{page-1}".encode()))
    if offset + per_page < total_count:
        nav_buttons.append(Button.inline("Next ➡️", f"admin_payments_{page+1}".encode()))
        
    buttons = [nav_buttons, [Button.inline("⬅️ Back to Admin Panel", b"admin_back")]] if nav_buttons else [[Button.inline("⬅️ Back to Admin Panel", b"admin_back")]]
    
    await event.edit(text, parse_mode='html', buttons=buttons)

@management_bot.on(events.CallbackQuery(pattern=b'admin_back'))
async def callback_back(event):
    if not is_admin(event.sender_id):
        return
    await event.edit(
        "<b>🛡️ Admin Control Panel</b>",
        parse_mode='html',
        buttons=[
            [Button.inline("📊 Stats", b"admin_stats"), Button.inline("👥 Merchants", b"admin_merchants")],
            [Button.inline("💰 Revenue", b"admin_revenue"), Button.inline("📈 Recent", b"admin_recent")],
            [Button.inline("⚠️ Errors", b"admin_errors"), Button.inline("📢 Broadcast", b"admin_broadcast")],
            [Button.inline("📊 View All Payments", b"admin_payments_0")],
            [Button.inline("❌ Close", b"admin_close")]
        ]
    )

@management_bot.on(events.CallbackQuery(pattern=b'admin_close'))
async def callback_close(event):
    if not is_admin(event.sender_id):
        return
    await event.delete()


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

    if current_state == "AWAITING_BROADCAST":
        if not text:
            await event.respond("❌ Broadcast message cannot be empty.")
            return
            
        await event.respond("⏳ Broadcasting to all merchants...")
        db = SessionLocal()
        merchants = db.query(Merchant).all()
        db.close()
        
        success_count = 0
        for m in merchants:
            try:
                if m.name.startswith("Merchant_"):
                    m_id = int(m.name.split("_")[1])
                    await management_bot.send_message(
                        m_id, 
                        f"📢 <b>Announcement from Admin</b>\n\n{text}",
                        parse_mode='html'
                    )
                    success_count += 1
            except Exception as e:
                logger.error(f"Failed to broadcast to {m.name}: {e}")
                
        user_states.pop(user_id, None)
        await event.respond(f"✅ Broadcast sent successfully to {success_count} merchants.")
        return

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
