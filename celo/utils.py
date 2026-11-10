from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.utils import timezone


def day_start(d: date) -> datetime:
    return timezone.make_aware(datetime.combine(d, time.min))


def range_start(days_back: int) -> datetime:
    """Start of the day `days_back` days ago (0 = today), timezone aware."""
    return day_start(timezone.localdate() - timedelta(days=days_back))


def day_end(d: date) -> datetime:
    return day_start(d + timedelta(days=1))


def require_positive_decimal(value, label):
    value = Decimal(value)
    if value <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return value
