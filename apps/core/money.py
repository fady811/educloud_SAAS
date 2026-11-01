"""Money helpers — EGP serialization (§16.7, REQ-NFR-09)."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

EGP = Decimal("0.01")  # 2 decimal places


def to_egp(value: Decimal | str | int | float) -> Decimal:
    """Normalize to 2dp EGP. Never pass floats from business logic."""
    return Decimal(str(value)).quantize(EGP, rounding=ROUND_HALF_UP)


def egp_str(value: Decimal) -> str:
    """Serialize to a decimal string as required (DR-020)."""
    return str(to_egp(value))
