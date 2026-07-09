import re
from typing import Optional, Dict, Any
from .base_parser import BaseParser


class PaymeParser(BaseParser):
    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        if 'payme' not in text.lower():
            return None

        amount_match = re.search(r'➕\s*([\d\s.,]+)\s*UZS', text)
        card_match = re.search(r'💳\s*([A-Za-z]+)\s*\*(\d{4})', text)

        if not amount_match:
            return None

        return {
            "amount_tiyins": self.extract_amount(amount_match.group(1)),
            "currency": "UZS",
            "card_type": card_match.group(1).upper() if card_match else "UNKNOWN",
            "receiver_card_info": f"*{card_match.group(2)}" if card_match else None,
            "source": "PAYME"
        }
