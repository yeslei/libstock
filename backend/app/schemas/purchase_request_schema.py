from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field


class PurchaseRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    book_id: int = Field(gt=0, le=2**63 - 1)
    pickup_date: date = Field(le=date(9998, 12, 31))


class PurchaseRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    book_id: int
    pickup_date: date
    status: str
    created_at: datetime
