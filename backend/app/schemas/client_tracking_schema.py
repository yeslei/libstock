from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class TrackingItem(BaseModel):
    id: int
    book_id: int
    title: str
    author: str
    cover_url: str | None
    status: Literal['AWAITING_PICKUP', 'ACTIVE', 'OVERDUE', 'WAITING', 'NOTIFIED']
    copy_barcode: str | None = None
    pickup_date: date | None = None
    due_date: date | None = None
    days_late: int = 0
    queue_position: int | None = None
    available_since: datetime | None = None
    expires_at: datetime | None = None
    expired: bool = False


class ReservePurchaseCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    book_id: int = Field(gt=0, le=2**63 - 1)


class ReservePurchaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    book_id: int
    status: Literal['WAITING']
    queue_position: int | None


class PickupConfirmation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    copy_id: int = Field(gt=0, le=2**63 - 1)


class CirculationResponse(BaseModel):
    id: int


class CancelReservationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str | None = Field(default=None, max_length=255)


class ExpireReservationsResponse(BaseModel):
    expired: int
