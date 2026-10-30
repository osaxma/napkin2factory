import pytest

from napkin2factory.core.units import (
    Quantity,
    UnitError,
    compare,
    format_quantity,
    mm,
    parse_quantity,
)


@pytest.mark.parametrize(
    "text", ["60 degC", "85 USD", "10 d", "1.5 mm", "200 mm", "3 kg", "0.5 kW"]
)
def test_roundtrip_d32(text):
    q = parse_quantity(text)
    assert format_quantity(q) == text


def test_dimensions():
    assert parse_quantity("85 USD").dimensionality == {"[currency]": 1}
    assert parse_quantity("10 d").to("hour").magnitude == 240
    assert parse_quantity("60 degC").to("kelvin").magnitude == pytest.approx(333.15)


def test_currency_is_its_own_dimension():
    with pytest.raises(Exception):
        parse_quantity("85 USD") + parse_quantity("10 mm")
    total = parse_quantity("85 USD") * 3 + parse_quantity("2.5 USD")
    assert format_quantity(total) == "257.5 USD"


def test_degc_comparison_and_offset_handling():
    assert compare(parse_quantity("55 degC"), "<", parse_quantity("60 degC"))
    assert compare(parse_quantity("333.15 kelvin"), "==", parse_quantity("60 degC"))
    # Constructing with Quantity(mag, unit) must not raise the offset error.
    assert Quantity(20, "degC").magnitude == 20


def test_bare_number_and_default_unit():
    assert format_quantity(parse_quantity("200")) == "200"
    assert format_quantity(parse_quantity(200, "mm")) == "200 mm"
    assert format_quantity(parse_quantity("200", "mm")) == "200 mm"


@pytest.mark.parametrize("bad", ["mm 50", "50 furlongs-per-fortnight", "", "abc", True])
def test_bad(bad):
    with pytest.raises(UnitError):
        parse_quantity(bad)


def test_compare_mismatch():
    with pytest.raises(UnitError):
        compare(parse_quantity("1 mm"), "<", parse_quantity("1 kg"))
    with pytest.raises(UnitError):
        compare(parse_quantity("1 mm"), "~", parse_quantity("1 mm"))


def test_mm_helper():
    assert mm(parse_quantity("2.5 cm")) == 25.0
    assert mm(3) == 3.0
