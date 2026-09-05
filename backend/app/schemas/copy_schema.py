from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.domain import CopyStatus, DestinationType

class CopyCreate(BaseModel):
    book_id: int = Field(gt=0, description="ID da obra à qual o exemplar pertence")
    barcode: str = Field(min_length=1, max_length=100, description="Código único do exemplar")
    destination: DestinationType = Field(description="Destinação do exemplar")
    condition: str | None = Field(default=None, max_length=30)
    sale_price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    acquired_at: date | None = None

    @model_validator(mode="after")
    def validate_sale_price(self) -> "CopyCreate":
        if self.destination == DestinationType.COMMERCIAL and self.sale_price is None:
            raise ValueError("sale_price é obrigatório para exemplares comerciais.")
        if self.destination == DestinationType.DIDACTIC and self.sale_price is not None:
            raise ValueError("sale_price não deve ser informado para exemplares didáticos.")
        return self

class CopyResponse(CopyCreate):
    id: int
    status: CopyStatus
    is_active: bool

    model_config = ConfigDict(from_attributes=True)