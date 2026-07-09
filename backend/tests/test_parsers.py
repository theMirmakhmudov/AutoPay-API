import pytest
from services.parsers.click_parser import ClickParser
from services.parsers.payme_parser import PaymeParser
from services.parsers.uzcard_parser import UzcardParser
from services.parsers.humo_parser import HumoParser

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
    ("➕ 35000 UZS\nHUMO *1234", 3500000),
    ("➕ 1234.56 UZS\nHUMO *1234", 123456),
    ("Invalid humo text without plus", None),
])
def test_humo_parser(message_text, expected_tiyins):
    parser = HumoParser()
    result = parser.parse(message_text)
    if expected_tiyins is None:
        assert result is None
    else:
        assert result["amount_tiyins"] == expected_tiyins
