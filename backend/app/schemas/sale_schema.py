from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.domain import SaleStatus


class SaleItemCreate(BaseModel):
    copy_id: int = Field(gt=0)
    unit_price: Decimal = Field(
        ge=0,
        max_digits=10,
        decimal_places=2,
    )


class SaleCreate(BaseModel):
    client_id: int | None = Field(default=None, gt=0)
    items: list[SaleItemCreate] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class SaleItemResponse(BaseModel):
    id: int
    sale_id: int
    copy_id: int
    unit_price: Decimal

    model_config = ConfigDict(from_attributes=True)


class SaleResponse(BaseModel):
    id: int
    client_id: int | None
    employee_id: int
    sale_date: datetime
    total_amount: Decimal
    status: SaleStatus
    items: list[SaleItemResponse]

    model_config = ConfigDict(from_attributes=True)