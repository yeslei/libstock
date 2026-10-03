"""Calendar rules shared by requests and circulation."""
from calendar import monthrange
from datetime import date, datetime
from zoneinfo import ZoneInfo

BUSINESS_ZONE = ZoneInfo("America/Sao_Paulo")


def next_month(value: date) -> date:
    year = value.year + (value.month == 12)
    month = value.month % 12 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def business_today() -> date:
    return datetime.now(BUSINESS_ZONE).date()
