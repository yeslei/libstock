import re
from datetime import date
from decimal import Decimal
from urllib.parse import urlparse

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


MAX_GENRE_IDS = 20


def _normalize_genre_ids(value: list[int] | None) -> list[int] | None:
    """Ids positivos, sem repetição e na ordem informada (Issue #174)."""
    if value is None:
        return None
    if any(item <= 0 or item > 2**63 - 1 for item in value):
        raise ValueError("Os ids de categoria devem ser inteiros positivos.")
    return list(dict.fromkeys(value))


class GenreRef(BaseModel):
    """Categoria do catálogo associada à obra."""

    id: int
    name: str
    slug: str

    model_config = ConfigDict(from_attributes=True)


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
        # Comercial sem preço ou com preço zero: 422 `copy_sale_price_required` no service (Issue #175).
        if self.destination == DestinationType.DIDACTIC and self.sale_price is not None:
            raise ValueError("Exemplar didático não pode possuir preço de venda.")
        return self


class BookCreate(BaseModel):
    isbn: str
    title: str | None = Field(default=None, max_length=255)
    author: str | None = Field(default=None, max_length=255)
    genre: str | None = Field(default=None, max_length=100)
    cover_url: str | None = Field(default=None, max_length=2048)
    publication_year: int | None = Field(default=None, ge=1000, le=2100)
    publisher: str | None = Field(default=None, max_length=150)
    # Categorias do catálogo (`GET /api/v1/catalog/genres?all=true`). Quando informado (mesmo vazio), é a
    # fonte da verdade: sincroniza `book_genres` e o texto `genre` passa a espelhar os nomes (Issue #174).
    genre_ids: list[int] | None = Field(default=None, max_length=MAX_GENRE_IDS)
    initial_copy: InitialCopyCreate

    model_config = ConfigDict(extra="forbid")

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, value: str) -> str:
        return normalize_isbn(value)

    @field_validator("title", "author", "genre", "cover_url", "publisher", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("genre_ids")
    @classmethod
    def validate_genre_ids(cls, value: list[int] | None) -> list[int] | None:
        return _normalize_genre_ids(value)

    @field_validator("cover_url")
    @classmethod
    def validate_cover_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("A capa deve ser uma URL HTTP ou HTTPS válida.")
        return value


class BookUpdate(BaseModel):
    isbn: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    author: str | None = Field(default=None, min_length=1, max_length=255)
    genre: str | None = Field(default=None, max_length=100)
    publication_year: int | None = Field(default=None, ge=1000, le=2100)
    publisher: str | None = Field(default=None, max_length=150)
    edition: str | None = Field(default=None, max_length=50)
    cover_url: str | None = Field(default=None, max_length=2048)
    is_active: bool | None = None
    genre_ids: list[int] | None = Field(default=None, max_length=MAX_GENRE_IDS)

    model_config = ConfigDict(extra="forbid")

    @field_validator("isbn")
    @classmethod
    def validate_optional_isbn(cls, value: str | None) -> str | None:
        return normalize_isbn(value) if value is not None else None

    @field_validator(
        "title", "author", "genre", "publisher", "edition", "cover_url", mode="before"
    )
    @classmethod
    def normalize_update_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("genre_ids")
    @classmethod
    def validate_update_genre_ids(cls, value: list[int] | None) -> list[int] | None:
        return _normalize_genre_ids(value)

    @field_validator("cover_url")
    @classmethod
    def validate_update_cover_url(cls, value: str | None) -> str | None:
        return BookCreate.validate_cover_url(value)

    @model_validator(mode="after")
    def require_change(self) -> "BookUpdate":
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualização.")
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("Título não pode ficar vazio.")
        if "author" in self.model_fields_set and self.author is None:
            raise ValueError("Autor não pode ficar vazio.")
        if "genre_ids" in self.model_fields_set and self.genre_ids is None:
            raise ValueError("A lista de categorias não pode ser nula; use [] para remover todas.")
        return self


class BookMetadataResponse(BaseModel):
    isbn: str
    title: str = Field(max_length=255)
    author: str = Field(max_length=255)
    genre: str | None = Field(default=None, max_length=100)
    cover_url: str | None = Field(default=None, max_length=2048)
    publisher: str | None = Field(default=None, max_length=150)
    publication_year: int | None = Field(default=None, ge=1000, le=2100)

class BookCreateResponse(BookCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)

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
    cover_url: str | None = None
    is_active: bool
    # Categorias do catálogo (book_genres); `genre` é o texto legado, espelho dos nomes (Issue #174).
    genres: list[GenreRef] = Field(default_factory=list)
    initial_copy: CopyResponse | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("genres", mode="before")
    @classmethod
    def unwrap_genre_links(cls, value: object) -> object:
        """Aceita as associações do ORM (`BookGenre`) ou as categorias diretamente, em ordem alfabética."""
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            genres = [getattr(item, "genre", item) for item in value]
            return sorted(genres, key=lambda item: (getattr(item, "name", "") or "").casefold())
        return value


class BookAvailabilityResponse(BaseModel):
    id: int
    title: str
    is_available: bool
    available_copies_count: int

    model_config = ConfigDict(from_attributes=True)


class BookDetailResponse(BookResponse):
    publication_year: int | None = None
    publisher: str | None = None
    edition: str | None = None
    copies: list[CopyResponse] = Field(default_factory=list)
