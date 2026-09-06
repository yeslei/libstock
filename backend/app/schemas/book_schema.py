import re
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.domain import CopyStatus, DestinationType


def normalize_isbn(value: str) -> str:
    """Valida ISBN-10/ISBN-13 e devolve a representação canônica compacta."""
    if not isinstance(value, str):
        raise ValueError("ISBN deve ser uma string.")

    raw_value = value.strip().upper()
    if not raw_value or re.fullmatch(r"[0-9X\s-]+", raw_value) is None:
        raise ValueError("ISBN inválido.")

    compact = re.sub(r"[\s-]", "", raw_value)
    if len(compact) == 10:
        if not compact[:9].isdigit() or not (compact[-1].isdigit() or compact[-1] == "X"):
            raise ValueError("ISBN-10 inválido.")
        digits = [int(character) for character in compact[:9]]
        check_digit = 10 if compact[-1] == "X" else int(compact[-1])
        if (sum((10 - index) * digit for index, digit in enumerate(digits)) + check_digit) % 11:
            raise ValueError("Checksum do ISBN-10 inválido.")
        return compact

    if len(compact) == 13 and compact.isdigit() and compact.startswith(("978", "979")):
        weighted_sum = sum(
            int(character) * (1 if index % 2 == 0 else 3)
            for index, character in enumerate(compact[:12])
        )
        expected_check_digit = (10 - weighted_sum % 10) % 10
        if int(compact[-1]) != expected_check_digit:
            raise ValueError("Checksum do ISBN-13 inválido.")
        return compact

    raise ValueError("ISBN deve possuir 10 ou 13 caracteres numéricos.")


class InitialCopyCreate(BaseModel):
    barcode: str = Field(min_length=1, max_length=100)
    destination: DestinationType
    condition: str | None = Field(default=None, max_length=30)
    sale_price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    acquired_at: date | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("barcode", "condition", mode="before")
    @classmethod
    def normalize_copy_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @model_validator(mode="after")
    def validate_initial_state(self) -> "InitialCopyCreate":
        if self.destination == DestinationType.COMMERCIAL and self.sale_price is None:
            raise ValueError("Informe o preço do exemplar comercial.")
        if self.destination == DestinationType.DIDACTIC and self.sale_price is not None:
            raise ValueError("Exemplar didático não pode possuir preço de venda.")
        return self


class BookCreate(BaseModel):
    isbn: str
    title: str | None = Field(default=None, max_length=255)
    author: str | None = Field(default=None, max_length=255)
    genre: str | None = Field(default=None, max_length=100)
    initial_copy: InitialCopyCreate

    model_config = ConfigDict(extra="forbid")

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, value: str) -> str:
        return normalize_isbn(value)

    @field_validator("title", "author", "genre", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class BookSearchParams(BaseModel):
    title: str = Field(min_length=1, pattern=r".*\S.*")

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("O título da busca não pode estar vazio.")
        return normalized


class CopyResponse(BaseModel):
    id: int
    book_id: int
    barcode: str
    destination: DestinationType
    status: CopyStatus
    condition: str | None
    sale_price: Decimal | None
    acquired_at: date | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class BookResponse(BaseModel):
    id: int
    isbn: str | None = None
    title: str
    author: str
    genre: str | None = None
    is_active: bool
    initial_copy: CopyResponse | None = None

    model_config = ConfigDict(from_attributes=True)
