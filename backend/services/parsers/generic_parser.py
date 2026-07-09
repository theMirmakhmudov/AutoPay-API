import re
from typing import Optional, Dict, Any
from .base_parser import BaseParser

class GenericParser(BaseParser):
    """
    A generic parser that tries to extract amount and card info using common patterns.
    Once actual sample messages are provided, this can be split into specific 
    HumoParser and UzcardParser classes.
    """
    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        # Amount pattern: "➕ 35.000,00 UZS"
        # We look for the ➕ emoji, so it doesn't matter if it's Click, Payme, or Uzum!
        amount_match = re.search(r'➕\s*([\d.,]+)\s*(UZS)?', text, re.IGNORECASE)
        
        # Receiver card pattern: "💳 VISA *4183"
        card_match = re.search(r'💳\s*([A-Za-z]+)\s*\*(\d{4})', text, re.IGNORECASE)
        
        # Date pattern: "🕓 15:15 28.05.2026"
        date_match = re.search(r'🕓\s*([\d:.\s]+)', text, re.IGNORECASE)
        
        if amount_match:
            amount = self.extract_amount(amount_match.group(1))
            
            card_type = "UNKNOWN"
            receiver_card = None
            if card_match:
                card_type = card_match.group(1).upper() # e.g., VISA
                receiver_card = f"*{card_match.group(2)}" # e.g., *4183
                
            return {
                "amount": amount,
                "currency": "UZS",
                "card_type": card_type,
                "receiver_card_info": receiver_card
            }
        
        return None
