from pydantic import BaseModel, ConfigDict

from app.models.domain import NotificationChannel


class NotificationPreferenceUpdate(BaseModel):
    channel: NotificationChannel

    model_config = ConfigDict(extra="forbid")


class NotificationPreferenceResponse(BaseModel):
    channel: NotificationChannel
    email: str
