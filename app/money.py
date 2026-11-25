from decimal import Decimal, InvalidOperation

# Number of decimal places (ISO 4217 minor-unit exponent) per supported currency.
CURRENCY_EXPONENTS = {"USD": 2, "EUR": 2, "GBP": 2, "CNY": 2, "JPY": 0}

# Keeps every value and sum far inside SQLite's signed 64-bit INTEGER range.
MAX_MINOR = 10**15


class MoneyError(ValueError):
    pass


def to_minor(amount: str, currency: str) -> int:
    """Parse a positive decimal string like "12.34" into integer minor units (1234). Never uses floats."""
    if currency not in CURRENCY_EXPONENTS:
        raise MoneyError(f"unsupported currency {currency!r}")
    if not isinstance(amount, str):
        raise MoneyError("amount must be a decimal string, e.g. \"12.34\"")
    try:
        value = Decimal(amount.strip())
    except InvalidOperation:
        raise MoneyError(f"amount {amount!r} is not a number") from None
    if not value.is_finite() or value <= 0:
        raise MoneyError("amount must be greater than zero")
    exponent = CURRENCY_EXPONENTS[currency]
    minor = value.scaleb(exponent)
    if minor != minor.to_integral_value():
        raise MoneyError(f"{currency} allows at most {exponent} decimal places")
    if minor > MAX_MINOR:
        raise MoneyError("amount is too large")
    return int(minor)


def to_major(minor: int, currency: str) -> str:
    """Format integer minor units back to a decimal string: 1234 USD -> "12.34"."""
    exponent = CURRENCY_EXPONENTS[currency]
    return f"{Decimal(minor).scaleb(-exponent):.{exponent}f}"
