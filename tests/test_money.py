import pytest

from app.money import MoneyError, to_major, to_minor


@pytest.mark.parametrize(
    ("amount", "currency", "expected"),
    [
        ("12.34", "USD", 1234),
        ("0.01", "EUR", 1),
        ("100", "GBP", 10000),
        ("12.30", "CNY", 1230),
        ("500", "JPY", 500),
        ("0.1", "USD", 10),
    ],
)
def test_valid_amounts_become_integer_minor_units(amount, currency, expected):
    result = to_minor(amount, currency)
    assert result == expected and isinstance(result, int)


@pytest.mark.parametrize(
    ("amount", "currency"),
    [
        ("1.234", "USD"),
        ("1.5", "JPY"),
        ("-5", "USD"),
        ("0", "USD"),
        ("abc", "USD"),
        ("NaN", "USD"),
        ("Infinity", "USD"),
        ("10", "XYZ"),
        ("10", "usd"),
        (12.3, "USD"),
        (12, "USD"),
        ("10000000000000.01", "USD"),
    ],
)
def test_bad_amounts_are_rejected(amount, currency):
    with pytest.raises(MoneyError):
        to_minor(amount, currency)


@pytest.mark.parametrize(
    ("minor", "currency", "expected"),
    [(1234, "USD", "12.34"), (-5, "USD", "-0.05"), (1200, "EUR", "12.00"), (0, "USD", "0.00"), (500, "JPY", "500")],
)
def test_to_major_round_trips(minor, currency, expected):
    assert to_major(minor, currency) == expected
