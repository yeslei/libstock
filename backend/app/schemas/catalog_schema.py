from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    """

    destination: DestinationType
    price: Decimal | None = None


class CatalogBookResponse(BaseModel):
    id: int
    title: str
    author: str
    cover_url: str | None = None
    genres: list[str] = []
    offers: list[BookOffer] = []

    model_config = ConfigDict(from_attributes=True)


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
