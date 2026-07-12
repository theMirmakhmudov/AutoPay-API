import re
from typing import Any, Dict, Optional

from .base_parser import BaseParser


class UzcardParser(BaseParser):
    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        amount_match = re.search(r'➕\s*([\d\s.,]+)\s*UZS', text)
        card_match = re.search(r'86\d{2}\s*\*+\s*\*+\s*(\d{4})', text)

        if not amount_match:
            return None

        return {
            "amount_tiyins": self.extract_amount(amount_match.group(1)),
            "currency": "UZS",
            "card_type": "UZCARD",
            "receiver_card_info": f"*{card_match.group(1)}" if card_match else None,
            "source": "UZCARD"
        }
