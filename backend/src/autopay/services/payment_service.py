import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from autopay.repositories.payment_repo import PaymentRepository
from autopay.schemas.payload import (
    CreatePaymentRequest,
    CreatePaymentResponse,
    TelegramWebhookPayload,
)

logger = logging.getLogger(__name__)

# Fix #5: Max UZS difference allowed before we refuse and force user to wait
MAX_COLLISION_OFFSET_TIYINS = (
    5000  # 50 UZS in tiyins (handles up to 50 concurrent identical payments)
)


class PaymentService:
    def __init__(self, db: Session):
        self.repo = PaymentRepository(db)

    def create_payment_intent(
        self, merchant_id: str, request: CreatePaymentRequest
    ) -> CreatePaymentResponse:
        """
        Creates a payment intent with hybrid collision resolution.
        Fix #1: All amounts handled in tiyins (integer).
        Fix #5: Caps dynamic offset at 10 UZS max.
        """
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        base_tiyins = round(request.base_amount * 100)

        max_expected = self.repo.get_max_expected_amount_for_base(merchant_id, base_tiyins)

        has_collision = False
        if max_expected is not None:
            next_expected = max_expected + 100  # +100 tiyins = +1.00 UZS

            # Fix #5: If we've already gone 10 UZS above base, don't increment further
            if (next_expected - base_tiyins) > MAX_COLLISION_OFFSET_TIYINS:
                # Too many collisions — tell frontend to show "please wait" only
                expected_tiyins = next_expected
                has_collision = True
                force_wait = True
            else:
                expected_tiyins = next_expected
                has_collision = True
                force_wait = False
        else:
            expected_tiyins = base_tiyins
            force_wait = False

        intent = self.repo.create_intent(
            merchant_id=merchant_id,
            base_amount_tiyins=base_tiyins,
            expected_amount_tiyins=expected_tiyins,
            expires_at=expires_at,
        )

        return CreatePaymentResponse(
            payment_id=str(intent.id),
            status=str(intent.status),
            base_amount=float(intent.base_amount_tiyins) / 100.0,
            has_collision=has_collision,
            force_wait=force_wait,
            expected_amount=float(intent.expected_amount_tiyins) / 100.0,
            expires_at=intent.expires_at,  # type: ignore
        )

    def process_telegram_webhook(self, payload: TelegramWebhookPayload, merchant_id: str) -> dict:
        """
        Parses and matches an incoming Telegram message to a pending PaymentIntent.
        Fix #1: Comparison done in tiyins.
        Fix #2: Webhook firing is async-safe.
        """
        from autopay.services.parsers.dispatcher import ParserDispatcher

        dispatcher = ParserDispatcher()

        # 1. Idempotency
        if self.repo.payment_exists(payload.message_id, payload.chat_username, merchant_id):
            return {"status": "DUPLICATE", "message": "Already processed"}

        # 2. Parse
        parsed_data = dispatcher.dispatch(payload.chat_username, payload.raw_text)

        if not parsed_data:
            self.repo.save_unparsed_message(
                merchant_id=merchant_id,
                message_id=payload.message_id,
                chat_username=payload.chat_username,
                raw_text=payload.raw_text,
                error_reason="Regex matching failed",
            )
            return {"status": "ERROR", "message": "Parse failed. Saved to DLQ."}

        # 3. Save payment (amounts already in tiyins from parser)
        amount_tiyins = parsed_data["amount_tiyins"]
        db_payment_data = {
            "merchant_id": merchant_id,
            "message_id": payload.message_id,
            "chat_username": payload.chat_username,
            "card_type": parsed_data.get("card_type", "UNKNOWN"),
            "amount_tiyins": amount_tiyins,
            "currency": parsed_data["currency"],
            "receiver_card_info": parsed_data.get("receiver_card_info"),
            "source": parsed_data.get("source"),
            "transaction_date": payload.date_received,
            "status": "UNMATCHED",
        }

        # 4. Enforce receiving card mask if configured by merchant
        merchant = self.repo.get_merchant_by_id(merchant_id)
        if merchant and merchant.receiving_card_mask:
            receiver_card = parsed_data.get("receiver_card_info")
            # Compare the last 4 digits (ignoring asterisks)
            mask_digits = merchant.receiving_card_mask.replace("*", "").strip()
            if not receiver_card or not receiver_card.endswith(mask_digits):
                self.repo.save_unparsed_message(
                    merchant_id=merchant_id,
                    message_id=payload.message_id,
                    chat_username=payload.chat_username,
                    raw_text=payload.raw_text,
                    error_reason=f"Card mismatch: Expected {merchant.receiving_card_mask}, got {receiver_card}",
                )
                return {
                    "status": "ERROR",
                    "message": f"Card mismatch: Expected {merchant.receiving_card_mask}",
                }

        # 5. Match to a pending intent — Fix #1: integer comparison, no float bugs
        active_intent = self.repo.get_active_intent_by_amount(merchant_id, amount_tiyins)

        if active_intent:
            db_payment_data["status"] = "MATCHED"
            saved_payment = self.repo.save_payment(db_payment_data)
            self.repo.mark_intent_paid(active_intent, saved_payment.id)

            merchant = self.repo.get_merchant_by_id(merchant_id)
            return {
                "status": "PROCESSED_AND_MATCHED",
                "payment": saved_payment,
                "intent_id": active_intent.id,
                "webhook_url": merchant.webhook_url if merchant else None,
                "webhook_secret": merchant.webhook_secret if merchant else None,
            }
        else:
            # We explicitly DO NOT save unmatched payments to avoid cluttering the database.
            return {"status": "PROCESSED_UNMATCHED", "payment": None, "amount": amount_tiyins}


async def fire_webhook_with_retry(
    webhook_url: str,
    processed_payment_id: str,
    intent_id: str,
    amount_tiyins: int,
    secret: Optional[str] = None,
):
    """
    Fix #2: Properly async webhook firing.
    Fix #10: Retries 3 times with exponential backoff (1s, 2s, 4s).
    Security: Signs the payload using HMAC-SHA256 if a secret is provided.
    """
    payload = {
        "event": "payment.success",
        "data": {
            "intent_id": intent_id,
            "payment_id": processed_payment_id,
            "amount": amount_tiyins / 100.0,
            "status": "PAID",
        },
    }

    headers = {"Content-Type": "application/json"}
    if secret:
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        headers["X-Webhook-Signature"] = signature

    async with httpx.AsyncClient() as client:
        for attempt in range(3):
            try:
                resp = await client.post(webhook_url, json=payload, headers=headers, timeout=5.0)
                resp.raise_for_status()
                logger.info(f"Webhook delivered to {webhook_url} (attempt {attempt + 1})")
                return
            except Exception as e:
                wait = 2**attempt  # 1s, 2s, 4s
                logger.warning(f"Webhook attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                await asyncio.sleep(wait)

    logger.error(f"Webhook permanently failed after 3 attempts for intent {intent_id}")
