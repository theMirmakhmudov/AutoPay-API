from datetime import datetime

from pydantic import BaseModel, Field

# --- Telegram Webhook Schemas ---

class TelegramWebhookPayload(BaseModel):
    message_id: int = Field(..., description="Unique message ID from Telegram")
    chat_username: str = Field(..., description="Username of the bank bot (e.g. 'clickuz')")
    raw_text: str = Field(..., description="Full raw text of the notification")
    date_received: datetime = Field(..., description="When the message was received")

# --- Payment API Schemas ---

class CreatePaymentRequest(BaseModel):
    base_amount: float = Field(..., description="Amount in UZS", json_schema_extra={"example": 35000})

class CreatePaymentResponse(BaseModel):
    payment_id: str = Field(..., description="Unique payment ID to poll for status")
    status: str
    base_amount: float
    has_collision: bool = Field(..., description="True if someone else is paying the same amount right now")
    force_wait: bool = Field(False, description="True if dynamic offset > 10 UZS — tell user to wait")
    expected_amount: float = Field(..., description="The exact amount the user MUST transfer")
    expires_at: datetime

class PaymentStatusResponse(BaseModel):
    payment_id: str
    status: str  # PENDING | PAID | EXPIRED | CANCELLED
    expected_amount: float
    expires_at: datetime

