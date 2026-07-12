from datetime import datetime

from pydantic import BaseModel


class MerchantView(BaseModel):
    id: str
    name: str
    api_key: str
    phone_number: str | None
    is_connected: bool
    webhook_url: str | None
    created_at: datetime

    class Config:
        from_attributes = True
