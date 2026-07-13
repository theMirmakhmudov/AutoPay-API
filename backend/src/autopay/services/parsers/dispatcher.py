from typing import Any, Dict, Optional

from .humo_parser import HumoParser

# Maps known Telegram bot usernames to their dedicated parser
BOT_PARSER_MAP = {
    "humocardbot": HumoParser(),
}

# The known bot usernames we should listen to in the userbot client
KNOWN_BOT_USERNAMES = list(BOT_PARSER_MAP.keys())

# Fallback parser tries all strategies on unknown senders
_generic_parsers = [HumoParser()]


class ParserDispatcher:
    """
    Routes incoming messages to the correct parser based on who sent them.
    If the sender is unknown, it tries each parser in order (generic fallback).
    """

    def dispatch(self, sender_username: str, raw_text: str) -> Optional[Dict[str, Any]]:
        username = (sender_username or "").lower()

        # Try the dedicated parser first
        if username in BOT_PARSER_MAP:
            result = BOT_PARSER_MAP[username].parse(raw_text)
            if result:
                return result

        # Generic fallback — try all parsers in order
        for parser in _generic_parsers:
            result = parser.parse(raw_text)
            if result:
                return result

        return None
