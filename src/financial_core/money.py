"""Explicit currency scales and context-independent integer arithmetic."""

import re
from decimal import Decimal


class AccountingError(ValueError):
    """Stable internal code; API error-envelope mapping belongs to Role 4."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def minor_units(amount: Decimal | str, scale: int) -> int:
    if not isinstance(scale, int) or isinstance(scale, bool) or not 0 <= scale <= 6:
        raise AccountingError("INVALID_CURRENCY_SCALE")
    if not isinstance(amount, (str, Decimal)):
        raise AccountingError("INVALID_MONEY")
    text = format(amount, "f") if isinstance(amount, Decimal) else amount
    if not re.fullmatch(r"(?:0|[1-9]\d*)(?:\.\d+)?", text) or len(text) > 100:
        raise AccountingError("INVALID_MONEY")
    whole, _, fraction = text.partition(".")
    if any(char != "0" for char in fraction[scale:]):
        raise AccountingError("CURRENCY_PRECISION")
    units = int(whole) * 10**scale + int(fraction[:scale].ljust(scale, "0") or "0")
    if units <= 0:
        raise AccountingError("INVALID_MONEY")
    return int(units)


def decimal_amount(units: int, scale: int) -> Decimal:
    sign = "-" if units < 0 else ""
    whole, fraction = divmod(abs(units), 10**scale)
    return Decimal(f"{sign}{whole}.{fraction:0{scale}d}" if scale else f"{sign}{whole}")
