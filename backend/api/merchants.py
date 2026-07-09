from fastapi import APIRouter, Depends
from core.security import get_current_merchant
from schemas.merchant import MerchantView
from schemas.base import BaseResponse, create_success_response
from models.payment import Merchant

router = APIRouter()

@router.get(
    "/me",
    response_model=BaseResponse[MerchantView],
    summary="View my credentials",
    description="Returns your Merchant ID, API Key, Telegram connection status, and configured webhook URL."
)
def get_my_credentials(merchant: Merchant = Depends(get_current_merchant)):
    return create_success_response(
        data=MerchantView.model_validate(merchant),
        message="Credentials fetched"
    )
