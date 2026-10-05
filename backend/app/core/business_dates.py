"""Business-calendar values shared by circulation queries."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

BUSINESS_ZONE = ZoneInfo("America/Sao_Paulo")


def business_today() -> date:
    return datetime.now(BUSINESS_ZONE).date()


def overdue_cutoff(today: date | None = None) -> datetime:
    """An open loan is overdue before the start of the business day."""
    return datetime.combine(today or business_today(), time.min, BUSINESS_ZONE)
