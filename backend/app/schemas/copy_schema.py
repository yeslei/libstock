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
        # Comercial sem preço ou com preço zero é regra de domínio (422 `copy_sale_price_required`, Issue #175),
        # aplicada no service, igual na inclusão e na edição.
        if self.destination == DestinationType.DIDACTIC and self.sale_price is not None:
            raise ValueError("sale_price não deve ser informado para exemplares didáticos.")
        return self

class CopyUpdate(BaseModel):
    """Edição/conversão de exemplar. O código (`barcode`) é imutável: campo não aceito."""

    destination: DestinationType | None = None
    condition: str | None = Field(default=None, max_length=30)
    sale_price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    acquired_at: date | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_update(self) -> "CopyUpdate":
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualização.")
        if "destination" in self.model_fields_set and self.destination is None:
            raise ValueError("A destinação não pode ficar vazia.")
        if self.destination == DestinationType.DIDACTIC and self.sale_price is not None:
            raise ValueError("sale_price não deve ser informado para exemplares didáticos.")
        return self


class CopyBatchCreate(BaseModel):
    copies: list[CopyCreate] = Field(
        min_length=1,
        description="Lista de exemplares físicos a serem cadastrados em uma única operação",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_same_book(self) -> "CopyBatchCreate":
        book_ids = {copy.book_id for copy in self.copies}

        if len(book_ids) != 1:
            raise ValueError(
                "Todos os exemplares da operação devem pertencer à mesma obra."
            )

        return self

class CopyResponse(CopyCreate):
    id: int
    status: CopyStatus
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class CopyDeleteResponse(BaseModel):
    id: int
    book_id: int
    barcode: str
    deleted: bool = True
