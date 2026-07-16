from fastapi import APIRouter, BackgroundTasks, Depends

from autopay.core.security import get_current_merchant
from autopay.models.payment import Merchant
from autopay.schemas.base import BaseResponse, create_success_response
from autopay.schemas.merchant import MerchantView

router = APIRouter()


@router.get(
    "/me",
    response_model=BaseResponse[MerchantView],
    summary="View my credentials",
    description="Returns your Merchant ID, API Key, Telegram connection status, and configured webhook URL.",
)
def get_my_credentials(merchant: Merchant = Depends(get_current_merchant)):
    return create_success_response(
        data=MerchantView.model_validate(merchant), message="Credentials fetched"
    )


@router.post(
    "/test-webhook",
    response_model=BaseResponse[dict],
    summary="Test Webhook Delivery",
    description="Fires a dummy webhook event to your configured webhook URL so you can test your integration in Postman.",
)
def test_webhook(
    background_tasks: BackgroundTasks, merchant: Merchant = Depends(get_current_merchant)
):
    import uuid

    from fastapi import HTTPException

    from autopay.services.payment_service import fire_webhook_with_retry

    if not merchant.webhook_url:
        raise HTTPException(status_code=400, detail="No webhook URL configured.")

    dummy_payment_id = f"test_pay_{uuid.uuid4().hex[:8]}"
    dummy_intent_id = f"test_intent_{uuid.uuid4().hex[:8]}"

    background_tasks.add_task(
        fire_webhook_with_retry,
        merchant.webhook_url,
        dummy_payment_id,
        dummy_intent_id,
        5000000,  # 50,000 UZS
        merchant.webhook_secret,
    )

    return create_success_response(
        data={
            "webhook_url": merchant.webhook_url,
            "dummy_payment_id": dummy_payment_id,
            "dummy_intent_id": dummy_intent_id,
            "amount": 50000.0,
        },
        message="Test webhook fired successfully in the background.",
    )
