"""Cairo-aware date/time helpers (§16.6, REQ-NFR-08)."""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytz
from dateutil.relativedelta import relativedelta
from django.utils import timezone

CAIRO_TZ = pytz.timezone("Africa/Cairo")


def now() -> datetime.datetime:
    """Return current time as UTC-aware datetime."""
    return timezone.now()


def cairo_now() -> datetime.datetime:
    """Return current time in Africa/Cairo."""
    return now().astimezone(CAIRO_TZ)


def cairo_date() -> datetime.date:
    """Return today's date in Africa/Cairo (use for all date-boundary business logic)."""
    return cairo_now().date()


def to_cairo(dt: datetime.datetime) -> datetime.datetime:
    return dt.astimezone(CAIRO_TZ)


def period_start_for(anchor: datetime.date, reference: datetime.date) -> datetime.date:
    """
    Return the start of the billing period that contains `reference`,
    given a per-student anniversary `anchor` (Q-06, INV-57).
    Handles 29/30/31 anchor days safely.
    """
    # Find the period start: the latest anchor-day that is <= reference
    year, month = reference.year, reference.month
    anchor_day = min(anchor.day, _days_in_month(year, month))
    period_start = datetime.date(year, month, anchor_day)
    if period_start > reference:
        # Roll back one month
        prev = datetime.date(year, month, 1) - relativedelta(months=1)
        anchor_day = min(anchor.day, _days_in_month(prev.year, prev.month))
        period_start = datetime.date(prev.year, prev.month, anchor_day)
    return period_start


def period_end_for(anchor: datetime.date, reference: datetime.date) -> datetime.date:
    """Return the end of the billing period (exclusive) containing `reference`."""
    start = period_start_for(anchor, reference)
    next_month = datetime.date(start.year, start.month, 1) + relativedelta(months=1)
    anchor_day = min(anchor.day, _days_in_month(next_month.year, next_month.month))
    return datetime.date(next_month.year, next_month.month, anchor_day)


def _days_in_month(year: int, month: int) -> int:
    import calendar
    return calendar.monthrange(year, month)[1]


def add_duration_days(dt: datetime.datetime, days: int) -> datetime.datetime:
    return dt + datetime.timedelta(days=days)


def remaining_days(expires_at: datetime.datetime) -> int:
    delta = expires_at - now()
    return max(0, delta.days)
