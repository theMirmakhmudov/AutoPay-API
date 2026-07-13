import pytest

from autopay.services.parsers.click_parser import ClickParser
from autopay.services.parsers.humo_parser import HumoParser
from autopay.services.parsers.payme_parser import PaymeParser
from autopay.services.parsers.uzcard_parser import UzcardParser


@pytest.mark.parametrize("message_text,expected_tiyins", [
    ("🎉 To'ldirish\n➕ 35.000,00 UZS\n💳 VISA *4183", 3500000),
    ("🎉 To'ldirish\n➕ 1.234,56 UZS\n💳 VISA *4183", 123456),
    ("Invalid message without plus", None),
])
def test_click_parser(message_text, expected_tiyins):
    parser = ClickParser()
    result = parser.parse(message_text)
    if expected_tiyins is None:
        assert result is None
    else:
        assert result["amount_tiyins"] == expected_tiyins

@pytest.mark.parametrize("message_text,expected_tiyins", [
    ("Payme\n➕ 35 000,00 UZS", 3500000),
    ("PAYME transfer\n➕ 1 234,56 UZS", 123456),
    ("Invalid payme string without plus", None),
])
def test_payme_parser(message_text, expected_tiyins):
    parser = PaymeParser()
    result = parser.parse(message_text)
    if expected_tiyins is None:
        assert result is None
    else:
        assert result["amount_tiyins"] == expected_tiyins

@pytest.mark.parametrize("message_text,expected_tiyins", [
    ("➕ 35000.00 UZS\n8612 **** **** 4183", 3500000),
    ("➕ 1234.56 UZS", 123456),
    ("Some random text without plus", None),
])
def test_uzcard_parser(message_text, expected_tiyins):
    parser = UzcardParser()
    result = parser.parse(message_text)
    if expected_tiyins is None:
        assert result is None
    else:
        assert result["amount_tiyins"] == expected_tiyins

@pytest.mark.parametrize("message_text,expected_tiyins", [
    ("🎉 To'ldirish\n➕ 35000 UZS\nHUMO *1234", 3500000),
    ("To'ldirish ➕ 1234.56 UZS\nHUMO *1234", 123456),
    ("➕ 35000 UZS\nHUMO *1234 (Missing word)", None),
    ("Invalid humo text without plus", None),
])
def test_humo_parser(message_text, expected_tiyins):
    parser = HumoParser()
    result = parser.parse(message_text)
    if expected_tiyins is None:
        assert result is None
    else:
        assert result["amount_tiyins"] == expected_tiyins

from autopay.services.parsers.base_parser import BaseParser
from autopay.services.parsers.cardxabar_parser import CardXabarParser
from autopay.services.parsers.dispatcher import ParserDispatcher
from autopay.services.parsers.generic_parser import GenericParser


def test_base_parser_extract_amount():
    parser = BaseParser()
    assert parser.extract_amount("35.000,00") == 3500000
    assert parser.extract_amount("35 000,00") == 3500000
    assert parser.extract_amount("500,000") == 50000000
    assert parser.extract_amount("35000") == 3500000
    assert parser.extract_amount("invalid") == 0

def test_base_parser_not_implemented():
    parser = BaseParser()
    try:
        parser.parse("test")
    except NotImplementedError:
        pass

def test_generic_parser():
    parser = GenericParser()
    # Test valid message
    msg = "➕ 35.000,00 UZS 💳 VISA *4183 🕓 15:15 28.05.2026"
    result = parser.parse(msg)
    assert result is not None
    assert result["amount_tiyins"] == 3500000
    assert result["card_type"] == "VISA"
    assert result["receiver_card_info"] == "*4183"

    # Test msg without card
    msg_no_card = "➕ 35.000,00 UZS 🕓 15:15"
    result_no_card = parser.parse(msg_no_card)
    assert result_no_card is not None
    assert result_no_card["amount_tiyins"] == 3500000
    assert result_no_card["card_type"] == "UNKNOWN"
    assert result_no_card["receiver_card_info"] is None

    # Test invalid message
    msg_invalid = "No money here"
    result_invalid = parser.parse(msg_invalid)
    assert result_invalid is None

def test_dispatcher():
    dispatcher = ParserDispatcher()

    # Dispatcher now strictly falls back to HumoParser, which requires "To'ldirish" and "UZS"
    msg = "To'ldirish ➕ 100 UZS 💳 VISA *4183"
    result = dispatcher.dispatch("unknown_bot", msg)
    assert result is not None
    assert result["amount_tiyins"] == 10000
    assert result["card_type"] == "VISA"

    # Test no match
    assert dispatcher.dispatch("unknown_bot", "blah blah") is None

def test_cardxabar_parser():
    parser = CardXabarParser()
    assert parser.parse("blah") is None
