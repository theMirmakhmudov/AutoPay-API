import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .base import Base


def generate_uuid():
    return str(uuid.uuid4())

class Merchant(Base):
    """
    A tenant on the SaaS platform.
    """
    __tablename__ = "merchants"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)

    # API key is NEVER stored — only its SHA-256 hash
    api_key_hash = Column(String, unique=True, index=True, nullable=False)

    # Telethon session is stored encrypted with Fernet (AES-128)
    phone_number = Column(String, nullable=True)
    encrypted_session = Column(String, nullable=True)
    is_connected = Column(Boolean, default=False)

    # Outbound webhook URL for the merchant's own bot backend
    webhook_url = Column(String, nullable=True)
    webhook_secret = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    payments = relationship("ProcessedPayment", back_populates="merchant")
    intents = relationship("PaymentIntent", back_populates="merchant")

class PaymentIntent(Base):
    """
    An invoice waiting to be paid. Amounts stored in TIYINS (integer) to avoid float bugs.
    """
    __tablename__ = "payment_intents"

    id = Column(String, primary_key=True, default=generate_uuid)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False)

    # Fix #1: Stored as INTEGER TIYINS (35000 UZS = 3500000 tiyins)
    base_amount_tiyins = Column(BigInteger, nullable=False)
    expected_amount_tiyins = Column(BigInteger, nullable=False)

    currency = Column(String, default="UZS")
    status = Column(String, default="PENDING")  # PENDING, PAID, EXPIRED, CANCELLED

    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    matched_payment_id = Column(Integer, ForeignKey("processed_payments.id"), nullable=True)

    merchant = relationship("Merchant", back_populates="intents")
    matched_payment = relationship("ProcessedPayment", foreign_keys=[matched_payment_id])

    @property
    def base_amount(self) -> float:
        """Convenience property for displaying amount in UZS."""
        return float(self.base_amount_tiyins) / 100.0 if self.base_amount_tiyins else 0.0

    @property
    def expected_amount(self) -> float:
        return float(self.expected_amount_tiyins) / 100.0 if self.expected_amount_tiyins else 0.0

class ProcessedPayment(Base):
    """
    A raw transaction successfully parsed from the Telegram Userbot.
    Amounts stored in TIYINS.
    """
    __tablename__ = "processed_payments"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False)

    message_id = Column(Integer, index=True, nullable=False)
    chat_username = Column(String, index=True, nullable=False)

    card_type = Column(String, nullable=False)
    amount_tiyins = Column(BigInteger, nullable=False)  # Fix #1: integer tiyins
    currency = Column(String, default="UZS")
    receiver_card_info = Column(String, nullable=True)
    source = Column(String, nullable=True)  # CLICK, UZCARD, HUMO, PAYME

    transaction_date = Column(DateTime, nullable=True)
    date_received = Column(DateTime, default=datetime.utcnow)

    status = Column(String, default="UNMATCHED")  # UNMATCHED, MATCHED

    merchant = relationship("Merchant", back_populates="payments")

    @property
    def amount(self) -> float:
        return float(self.amount_tiyins) / 100.0 if self.amount_tiyins else 0.0

class UnparsedMessage(Base):
    """
    Dead Letter Queue for failed regex parsing.
    """
    __tablename__ = "unparsed_messages"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=True)
    message_id = Column(Integer, index=True, nullable=False)
    chat_username = Column(String, index=True, nullable=False)

    raw_text = Column(Text, nullable=False)
    error_reason = Column(String, nullable=False)
    date_received = Column(DateTime, default=datetime.utcnow)
    is_resolved = Column(Boolean, default=False)
