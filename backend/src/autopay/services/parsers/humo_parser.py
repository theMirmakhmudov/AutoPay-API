import re
from typing import Any, Dict, Optional

from .base_parser import BaseParser


class HumoParser(BaseParser):
    """
    Parser for @humocardbot messages.
    """
    # Pre-compile regex patterns for performance and better maintainability
    _ACTION_PATTERN = re.compile(r"to'ldirish", re.IGNORECASE)
    _AMOUNT_PATTERN = re.compile(r"➕\s*([\d\s.,]+)\s*UZS", re.IGNORECASE)
    _CARD_PATTERN = re.compile(r"💳\s*([A-Za-z]+)?\s*\*(\d{4})", re.IGNORECASE)

    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        # 1. Validate transaction type (must be an incoming top-up)
        if not self._ACTION_PATTERN.search(text):
            return None

        # 2. Extract amount
        amount_match = self._AMOUNT_PATTERN.search(text)
        if not amount_match:
            return None

        # 3. Extract card details
        card_match = self._CARD_PATTERN.search(text)
        card_type = "HUMO"
        receiver_card_info = None

        if card_match:
            extracted_type = card_match.group(1)
            card_type = extracted_type.upper() if extracted_type else "HUMO"
            receiver_card_info = f"*{card_match.group(2)}"

        return {
            "amount_tiyins": self.extract_amount(amount_match.group(1)),
            "currency": "UZS",
            "card_type": card_type,
            "receiver_card_info": receiver_card_info,
            "source": "HUMO_BOT"
        }
