from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.domain import NotificationChannel, NotificationStatus


class NotificationResponse(BaseModel):
    id: int
    reservation_id: int | None
    type: str
    channel: NotificationChannel
    subject: str | None
    message: str
    status: NotificationStatus
    created_at: datetime
    sent_at: datetime | None
    read_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class NotificationPage(BaseModel):
    items: list[NotificationResponse]
    next_before_id: int | None
