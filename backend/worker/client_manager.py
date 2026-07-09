import asyncio
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from typing import Dict
from models.payment import Merchant
from services.payment_service import PaymentService, fire_webhook_with_retry
from services.parsers.dispatcher import KNOWN_BOT_USERNAMES
from schemas.payload import TelegramWebhookPayload
from core.database import SessionLocal
from core.encryption import decrypt_session

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
                    from worker.bot import management_bot
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
