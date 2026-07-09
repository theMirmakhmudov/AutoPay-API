import re
from typing import Optional, Dict, Any
from .base_parser import BaseParser


class HumoParser(BaseParser):
    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        amount_match = re.search(r'➕\s*([\d\s.,]+)\s*UZS', text)
        card_match = re.search(r'HUMO\s*\*(\d{4})', text, re.IGNORECASE)

        if not amount_match:
            return None

        return {
            "amount_tiyins": self.extract_amount(amount_match.group(1)),
            "currency": "UZS",
            "card_type": "HUMO",
            "receiver_card_info": f"*{card_match.group(1)}" if card_match else None,
            "source": "HUMO"
        }
