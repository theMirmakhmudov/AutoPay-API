from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from core.database import get_db
from core.security import get_current_merchant
from schemas.payload import TelegramWebhookPayload
from schemas.base import BaseResponse, create_success_response, create_error_response
from services.payment_service import PaymentService
from repositories.payment_repo import PaymentRepository
from models.payment import Merchant

router = APIRouter()


@router.post(
    "/telegram",
    response_model=BaseResponse[dict],
    summary="Receive Telegram Userbot notification",
    description=(
        "Called by the Telegram Userbot when a new payment notification arrives. "
        "Pass merchant_id as a query parameter so the platform knows which merchant "
        "this notification belongs to. Authentication is via the X-API-Key header."
    )
)
def receive_telegram_webhook(
    payload: TelegramWebhookPayload,
    merchant_id: str = Query(..., description="The merchant's unique ID to route this notification correctly"),
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant)
):
    # Ensure the merchant_id in the query param matches the authenticated merchant
    if merchant.id != merchant_id:
        return create_error_response(
            message="merchant_id does not match your API key",
            error_code="MERCHANT_MISMATCH"
        )

    service = PaymentService(db)
    result = service.process_telegram_webhook(payload, merchant.id)

    if result["status"] in ("PROCESSED_AND_MATCHED", "PROCESSED_UNMATCHED"):
        payment = result["payment"]
        matched = result["status"] == "PROCESSED_AND_MATCHED"
        return create_success_response(
            data={
                "matched": matched,
                "payment_id": str(payment.id),
                "amount": payment.amount,
                "source": payment.source,
            },
            message="Payment matched!" if matched else "Payment processed but not yet matched to any order"
        )
    elif result["status"] == "DUPLICATE":
        return create_success_response(
            data={"message_id": payload.message_id},
            message="Duplicate — already processed"
        )
    else:
        return create_error_response(
            message=result["message"],
            error_code="PARSE_ERROR"
        )
