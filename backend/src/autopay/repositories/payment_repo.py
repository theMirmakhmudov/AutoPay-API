from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.sql import text

from autopay.models.payment import Merchant, PaymentIntent, ProcessedPayment, UnparsedMessage


class PaymentRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Merchant ---
    def get_merchant_by_api_key(self, api_key_hash: str) -> Optional[Merchant]:
        return self.db.query(Merchant).filter(Merchant.api_key_hash == api_key_hash).first()

    def get_merchant_by_id(self, merchant_id: str) -> Optional[Merchant]:
        return self.db.query(Merchant).filter(Merchant.id == merchant_id).first()

    def update_merchant_webhook(self, merchant_id: str, webhook_url: str):
        """Fix #11: Allow merchants to update their webhook URL."""
        merchant = self.get_merchant_by_id(merchant_id)
        if merchant:
            merchant.webhook_url = webhook_url
            self.db.commit()
            self.db.refresh(merchant)
        return merchant

    # --- Intents ---
    def create_intent(self, merchant_id: str, base_amount_tiyins: int, expected_amount_tiyins: int, expires_at: datetime) -> PaymentIntent:
        intent = PaymentIntent(
            merchant_id=merchant_id,
            base_amount_tiyins=base_amount_tiyins,
            expected_amount_tiyins=expected_amount_tiyins,
            expires_at=expires_at
        )
        self.db.add(intent)
        self.db.commit()
        self.db.refresh(intent)
        return intent

    def get_intent(self, intent_id: str, merchant_id: str) -> Optional[PaymentIntent]:
        return self.db.query(PaymentIntent).filter(
            PaymentIntent.id == intent_id,
            PaymentIntent.merchant_id == merchant_id
        ).first()

    def get_active_intent_by_amount(self, merchant_id: str, amount_tiyins: int) -> Optional[PaymentIntent]:
        """
        Fix #1: Integer tiyin comparison — no float precision bugs possible.
        """
        now = datetime.now(timezone.utc)
        return self.db.query(PaymentIntent).filter(
            PaymentIntent.merchant_id == merchant_id,
            PaymentIntent.expected_amount_tiyins == amount_tiyins,  # Safe: integer comparison
            PaymentIntent.status == "PENDING",
            PaymentIntent.expires_at > now
        ).first()

    def get_max_expected_amount_for_base(self, merchant_id: str, base_amount_tiyins: int) -> Optional[int]:
        """
        Fix #5: Returns max expected tiyin value for collision detection.
        """
        now = datetime.now(timezone.utc)
        active_intents = self.db.query(PaymentIntent).filter(
            PaymentIntent.merchant_id == merchant_id,
            PaymentIntent.base_amount_tiyins == base_amount_tiyins,
            PaymentIntent.status == "PENDING",
            PaymentIntent.expires_at > now
        ).all()

        if not active_intents:
            return None

        return max(int(intent.expected_amount_tiyins) for intent in active_intents)

    def mark_intent_paid(self, intent: PaymentIntent, payment_id: int):
        intent.status = "PAID"  # type: ignore
        intent.matched_payment_id = payment_id
        self.db.commit()

        # Fire PostgreSQL NOTIFY for real-time WebSocket clients
        try:
            self.db.execute(text(f"NOTIFY payment_updates, '{intent.id}'"))
            self.db.commit()
        except Exception:
            pass # SQLite fallback during transition/testing

        self.db.refresh(intent)

    def expire_old_intents(self) -> int:
        """Fix #3/#8: Bulk expire — called by the cleanup worker. Returns count."""
        now = datetime.now(timezone.utc)
        expired = self.db.query(PaymentIntent).filter(
            PaymentIntent.status == "PENDING",
            PaymentIntent.expires_at <= now
        ).all()
        for intent in expired:
            intent.status = "EXPIRED"  # type: ignore
            intent.paid_amount_tiyins = 0  # type: ignore
        self.db.commit()
        return len(expired)

    # --- Webhook Processing ---
    def payment_exists(self, message_id: int, chat_username: str, merchant_id: str) -> bool:
        """Idempotency check scoped to merchant."""
        exists_processed = self.db.query(ProcessedPayment).filter(
            ProcessedPayment.message_id == message_id,
            ProcessedPayment.chat_username == chat_username,
            ProcessedPayment.merchant_id == merchant_id
        ).first()
        if exists_processed:
            return True

        exists_unparsed = self.db.query(UnparsedMessage).filter(
            UnparsedMessage.message_id == message_id,
            UnparsedMessage.chat_username == chat_username,
            UnparsedMessage.merchant_id == merchant_id
        ).first()
        return exists_unparsed is not None

    def save_payment(self, payment_data: dict) -> ProcessedPayment:
        payment = ProcessedPayment(**payment_data)
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def save_unparsed_message(self, message_id: int, chat_username: str, raw_text: str, error_reason: str, merchant_id: str) -> UnparsedMessage:
        unparsed = UnparsedMessage(
            merchant_id=merchant_id,
            message_id=message_id,
            chat_username=chat_username,
            raw_text=raw_text,
            error_reason=error_reason
        )
        self.db.add(unparsed)
        self.db.commit()
        self.db.refresh(unparsed)
        return unparsed
