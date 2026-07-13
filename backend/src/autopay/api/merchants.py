from fastapi import APIRouter, Depends

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
