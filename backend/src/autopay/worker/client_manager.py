import asyncio
import logging
from typing import Dict

from telethon import TelegramClient, errors, events
from telethon.sessions import StringSession

from autopay.core.config import settings
from autopay.core.database import SessionLocal
from autopay.core.encryption import decrypt_session
from autopay.models.payment import Merchant
from autopay.schemas.payload import TelegramWebhookPayload
from autopay.services.parsers.dispatcher import KNOWN_BOT_USERNAMES
from autopay.services.payment_service import PaymentService, fire_webhook_with_retry

logger = logging.getLogger(__name__)

class ClientManager:
    def __init__(self, api_id: int, api_hash: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.clients: Dict[str, TelegramClient] = {}

    async def start_all_clients(self):
        db = SessionLocal()
        merchants = db.query(Merchant).filter(
            Merchant.is_connected == True,
            Merchant.encrypted_session != None
        ).all()
        db.close()
        for merchant in merchants:
            await self.start_client(merchant)

    async def start_client(self, merchant: Merchant):
        if merchant.id in self.clients:
            return

        plain_session = decrypt_session(merchant.encrypted_session)
        client = TelegramClient(StringSession(plain_session), self.api_id, self.api_hash)

        # Capture merchant_id in closure to avoid late-binding bugs
        merchant_id = merchant.id

        @client.on(events.NewMessage(incoming=True))
        async def handler(event):
            sender = await event.get_sender()
            sender_username = (getattr(sender, 'username', None) or "").lower()

            if sender_username not in KNOWN_BOT_USERNAMES:
                return

            logger.info(f"[{merchant_id}] Notification from @{sender_username}")
            await self._handle_message(event, merchant_id, sender_username)

        try:
            await client.start()
            self.clients[merchant_id] = client
            logger.info(f"Userbot started for merchant {merchant_id}")
        except Exception as e:
            logger.error(f"Failed to start userbot for {merchant_id}: {e}")

    async def stop_client(self, merchant_id: str):
        client = self.clients.pop(merchant_id, None)
        if client:
            await client.disconnect()
            logger.info(f"Userbot stopped for merchant {merchant_id}")

    async def _handle_message(self, event, merchant_id: str, sender_username: str):
        db = SessionLocal()
        try:
            payload = TelegramWebhookPayload(
                message_id=event.id,
                chat_username=sender_username,
                raw_text=event.raw_text,
                date_received=event.date
            )

            service = PaymentService(db)
            result = service.process_telegram_webhook(payload, merchant_id)

            if result["status"] == "PROCESSED_AND_MATCHED":
                payment = result["payment"]
                intent_id = result["intent_id"]
                webhook_url = result.get("webhook_url")
                webhook_secret = result.get("webhook_secret")

                logger.info(f"[{merchant_id}] MATCHED intent={intent_id} amount={payment.amount} UZS")

                # Fix #2 + #10: Properly async, 3-attempt retry
                if webhook_url:
                    asyncio.create_task(
                        fire_webhook_with_retry(webhook_url, payment.id, intent_id, payment.amount, webhook_secret)
                    )

                # Notify merchant via Telegram
                try:
                    from autopay.worker.bot import management_bot
                    db = SessionLocal()
                    merchant_record = db.query(Merchant).filter(Merchant.id == merchant_id).first()
                    db.close()
                    if merchant_record and merchant_record.name.startswith("Merchant_"):
                        telegram_user_id = int(merchant_record.name.split("_")[1])
                        asyncio.create_task(
                            management_bot.send_message(
                                telegram_user_id,
                                f"✅ *Payment Received!*\n\nAmount: `{payment.amount:,.2f} UZS`\nStatus: `PAID`\nIntent ID: `{intent_id}`",
                                parse_mode='md'
                            )
                        )
                except Exception as notify_err:
                    logger.error(f"Failed to notify merchant {merchant_id} via Telegram: {notify_err}")

            elif result["status"] == "PROCESSED_UNMATCHED":
                logger.warning(f"[{merchant_id}] Unmatched payment — no open intent for this amount")

        except Exception as e:
            logger.error(f"Error handling message for {merchant_id}: {e}", exc_info=True)
        finally:
            db.close()

    async def health_check_clients(self):
        db = SessionLocal()
        from autopay.worker.bot import management_bot
        admin_ids = [int(x.strip()) for x in settings.ADMIN_TELEGRAM_IDS.split(",") if x.strip().isdigit()]

        # We must copy keys because we might modify the dict during iteration
        for merchant_id, client in list(self.clients.items()):
            try:
                await client.get_me()
            except errors.UnauthorizedError:
                logger.warning(f"Session revoked or unauthorized for merchant {merchant_id}")

                # Mark as disconnected
                merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
                if merchant:
                    merchant.is_connected = False
                    db.commit()

                    # Try notifying the merchant
                    if merchant.name.startswith("Merchant_"):
                        telegram_user_id = int(merchant.name.split("_")[1])
                        alert_msg = "⚠️ *CRITICAL ALERT* ⚠️\n\nYour Telegram session was disconnected or revoked! The bot can no longer read incoming payments.\n\nPlease use `/login` to reconnect your account immediately."
                        try:
                            await management_bot.send_message(telegram_user_id, alert_msg, parse_mode='md')
                        except Exception as e:
                            logger.error(f"Failed to notify merchant {merchant_id} of disconnect: {e}")

                    # Notify admins
                    admin_msg = f"🚨 *Merchant Disconnected*\n\nMerchant ID: `{merchant.id}`\nPhone: `{merchant.phone_number}`\n\nThe userbot session was terminated. They have been automatically marked as disconnected."
                    for admin_id in admin_ids:
                        try:
                            await management_bot.send_message(admin_id, admin_msg, parse_mode='md')
                        except Exception as e:
                            pass

                # Stop the client on our end
                await self.stop_client(merchant_id)
            except Exception as e:
                # Other exceptions (like network errors) shouldn't cause a forced disconnect
                logger.error(f"Error during health check for {merchant_id}: {e}")

        db.close()
