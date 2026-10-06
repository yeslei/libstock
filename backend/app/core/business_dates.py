"""Calendar rules shared by requests and circulation."""
from calendar import monthrange
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

BUSINESS_ZONE = ZoneInfo("America/Sao_Paulo")
RESERVATION_PICKUP_DAYS = 5


def next_month(value: date) -> date:
    year = value.year + (value.month == 12)
    month = value.month % 12 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def business_today() -> date:
    return datetime.now(BUSINESS_ZONE).date()


def loan_due_at(started_at: datetime) -> datetime:
    local = started_at.astimezone(BUSINESS_ZONE)
    return datetime.combine(next_month(local.date()), local.timetz())


def overdue_cutoff(today: date | None = None) -> datetime:
    return datetime.combine(today or business_today(), time.min, BUSINESS_ZONE)


def reservation_pickup_deadline(allocated_at: datetime) -> datetime:
    local_date = allocated_at.astimezone(BUSINESS_ZONE).date()
    return datetime.combine(
        local_date + timedelta(days=RESERVATION_PICKUP_DAYS),
        time(23, 59, 59, 999000),
        BUSINESS_ZONE,
    )
