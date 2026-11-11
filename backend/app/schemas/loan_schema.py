from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.domain import LoanStatus, NotificationChannel, NotificationStatus


class LoanCreate(BaseModel):
    client_id: int = Field(gt=0)
    copy_id: int = Field(gt=0)


class LoanResponse(BaseModel):
    id: int
    client_id: int
    copy_id: int
    employee_id: int
    loan_date: datetime
    due_date: datetime
    returned_at: datetime | None
    status: LoanStatus

    model_config = ConfigDict(from_attributes=True)


class ReturnReminderResponse(BaseModel):
    id: int
    loan_id: int
    client_id: int
    channel: NotificationChannel
    status: NotificationStatus
    subject: str
    message: str
    created_at: datetime
