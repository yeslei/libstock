from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.domain import DestinationType


class GenreResponse(BaseModel):
    id: int
    name: str
    slug: str

    model_config = ConfigDict(from_attributes=True)


class GenreCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    is_featured: bool = False
    display_order: int | None = Field(default=None, ge=1)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("O nome deve possuir pelo menos 2 caracteres.")
        return normalized


class FeaturedUpdate(BaseModel):
    """Corpo dos endpoints de destaque de livro e de gênero.

    `position` é opcional porque desligar o destaque não precisa de posição;
    a validação cruzada fica no service, que conhece a regra de negócio.
    """

    is_featured: bool
    position: int | None = Field(default=None, ge=1)


class BookOffer(BaseModel):
    """Como o livro está disponível hoje, derivado dos exemplares ativos.

    Não é coluna: é agregação sobre `copies`. Um mesmo livro pode estar à
    venda e disponível para empréstimo ao mesmo tempo.

    `available` falso é o "Esgotado" que a US02 exige sinalizar — o livro
    continua no catálogo, apenas sem exemplar livre. `can_reserve` marca o
    caso do RF07: exemplar de venda que está emprestado, e por isso admite
    Reserva de Compra.
    """

    destination: DestinationType
    available: bool
    price: Decimal | None = None
    can_reserve: bool = False


class CatalogBookResponse(BaseModel):
    id: int
    title: str
    author: str
    cover_url: str | None = None
    genres: list[str] = []
    offers: list[BookOffer] = []

    model_config = ConfigDict(from_attributes=True)


class CatalogSearchParams(BaseModel):
    title: str | None = None
    author: str | None = None

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "CatalogSearchParams":
        self.title = self.title.strip() if self.title is not None else None
        self.author = self.author.strip() if self.author is not None else None
        if not self.title and not self.author:
            raise ValueError("Informe título ou autor para a busca.")
        return self


class PagedBooksResponse(BaseModel):
    """Página de livros de um gênero.

    Carrega o gênero junto porque a tela precisa do nome exibível ("Não
    ficção") e o cliente só tem o slug ("nao-ficcao") — derivar um do outro
    no frontend perderia acento e caixa.
    """

    genre: GenreResponse
    items: list[CatalogBookResponse]
    total: int
    page: int
    page_size: int
