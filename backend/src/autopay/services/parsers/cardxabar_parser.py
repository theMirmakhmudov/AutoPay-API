import re
from typing import Any, Dict, Optional

from .base_parser import BaseParser


class CardXabarParser(BaseParser):
    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        # DRAFT: We don't have the exact format of @CardXabarBot yet.
        # This is a generic placeholder that looks for amounts and cards.
        amount_match = re.search(r"([\d\s.,]+)\s*UZS", text, re.IGNORECASE)
        card_match = re.search(r"\*(\d{4})", text)

        if not amount_match:
            return None

        return {
            "amount_tiyins": self.extract_amount(amount_match.group(1)),
            "currency": "UZS",
            "card_type": "UNKNOWN",
            "receiver_card_info": f"*{card_match.group(1)}" if card_match else None,
            "source": "CARD_XABAR",
        }
