import re
from typing import Any, Dict, Optional

# Pre-compile regex patterns for amount formatting to improve performance
_WHITESPACE_PATTERN = re.compile(r'\s+')
_NON_DIGIT_PATTERN = re.compile(r'[^\d.]')


class BaseParser:
    """
    Abstract base class for all bot parsers.
    """

    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError()

    @staticmethod
    def extract_amount(amount_str: str) -> int:
        """
        Converts Uzbek-format amount strings to integer TIYINS.
        This avoids all float precision issues for money comparison.

        Examples:
          "35.000,00" -> 3500000   (35000 UZS in tiyins)
          "35 000,00" -> 3500000
          "500,000"   -> 50000000  (500000 UZS in tiyins, assuming English comma if no dot)
          "35000"     -> 3500000
        """
        # Remove all whitespace efficiently
        amount_str = _WHITESPACE_PATTERN.sub('', amount_str)

        # If it has both dot and comma, assume European (1.234,56)
        if '.' in amount_str and ',' in amount_str:
            amount_str = amount_str.replace('.', '').replace(',', '.')
        # If it has only comma
        elif ',' in amount_str:
            # If the comma is exactly 2 places from the end (e.g. 35000,00), it's a decimal
            if amount_str[-3] == ',':
                amount_str = amount_str.replace(',', '.')
            else:
                # Otherwise it's probably a thousands separator (e.g. 500,000)
                amount_str = amount_str.replace(',', '')

        # Remove everything except digits and dot
        clean_str = _NON_DIGIT_PATTERN.sub('', amount_str)
        try:
            return round(float(clean_str) * 100)  # store as tiyins (integer)
        except ValueError:
            return 0
