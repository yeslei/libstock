import re
import unicodedata
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AuditActorRequiredError,
    BookNotFoundError,
    DuplicateGenreError,
    GenreNotFoundError,
)
from app.models.domain import Book, CopyStatus, DestinationType, Genre
from app.repositories.catalog_repository import CatalogRepository, GenreRepository
from app.schemas.catalog_schema import (
    BookOffer,
    CatalogBookResponse,
    FeaturedUpdate,
    GenreCreate,
    GenreResponse,
    PagedBooksResponse,
)

FEATURED_BOOKS_LIMIT = 12


def slugify(value: str) -> str:
    """Reduz o nome a um slug ASCII estável.

    "Não ficção" precisa virar "nao-ficcao" e não "no-fico": a decomposição
    NFKD separa o acento da letra base antes do descarte, preservando a letra.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
    if not slug:
        raise ValueError("O nome não gera um slug válido.")
    return slug


class CatalogService:
    def __init__(
        self,
        *,
        db: Session,
        catalog_repository: CatalogRepository,
        genre_repository: GenreRepository,
    ) -> None:
        self.db = db
        self.catalog_repository = catalog_repository
        self.genre_repository = genre_repository

    # ---- Leitura pública -------------------------------------------------

    def list_featured_books(self) -> list[CatalogBookResponse]:
        books = self.catalog_repository.find_featured_books(limit=FEATURED_BOOKS_LIMIT)
        return [self._to_response(book) for book in books]

    def list_featured_genres(self) -> list[Genre]:
        return self.genre_repository.find_featured()

    def list_books_by_genre(
        self,
        *,
        slug: str,
        page: int,
        page_size: int,
    ) -> PagedBooksResponse:
        genre = self.genre_repository.find_by_slug(slug)
        if genre is None:
            raise GenreNotFoundError()

        books, total = self.catalog_repository.find_books_by_genre(
            genre_id=genre.id,
            page=page,
            page_size=page_size,
        )
        return PagedBooksResponse(
            genre=GenreResponse.model_validate(genre),
            items=[self._to_response(book) for book in books],
            total=total,
            page=page,
            page_size=page_size,
        )

    # ---- Administração ---------------------------------------------------

    def create_genre(self, data_in: GenreCreate) -> Genre:
        slug = slugify(data_in.name)
        if self.genre_repository.exists_with_name_or_slug(name=data_in.name, slug=slug):
            raise DuplicateGenreError()

        try:
            genre = self.genre_repository.create(
                name=data_in.name,
                slug=slug,
                is_featured=data_in.is_featured,
                display_order=data_in.display_order,
            )
            self.db.commit()
            self.db.refresh(genre)
            return genre
        except IntegrityError as exc:
            # A checagem acima não protege contra duas criações simultâneas;
            # quem decide de verdade é a constraint UNIQUE.
            self.db.rollback()
            raise DuplicateGenreError() from exc

    def set_genre_featured(self, *, genre_id: int, data_in: FeaturedUpdate) -> Genre:
        genre = self.genre_repository.find_by_id(genre_id)
        if genre is None:
            raise GenreNotFoundError()

        genre.is_featured = data_in.is_featured
        # Tirar do destaque zera a posição: mantê-la deixaria um número órfão
        # que reapareceria fora de ordem no próximo destaque.
        genre.display_order = data_in.position if data_in.is_featured else None
        self.db.commit()
        self.db.refresh(genre)
        return genre

    def set_book_featured(
        self,
        *,
        book_id: int,
        data_in: FeaturedUpdate,
        actor_id: int,
    ) -> Book:
        """Altera o destaque de um livro.

        `books` é tabela de inventário auditada (RNF03): o banco recusa a
        escrita se a transação não declarar qual funcionário responde por
        ela. Por isso a operação exige o ator, e não apenas o papel.
        """
        if not self.catalog_repository.is_employee(actor_id):
            raise AuditActorRequiredError()
        self.catalog_repository.set_audit_actor(actor_id)

        book = self.catalog_repository.find_book_by_id(book_id)
        if book is None:
            raise BookNotFoundError()

        book.is_featured = data_in.is_featured
        book.featured_position = data_in.position if data_in.is_featured else None
        self.db.commit()
        self.db.refresh(book)
        return book

    # ---- Projeção --------------------------------------------------------

    def _to_response(self, book: Book) -> CatalogBookResponse:
        return CatalogBookResponse(
            id=book.id,
            title=book.title,
            author=book.author,
            cover_url=book.cover_url,
            genres=[link.genre.name for link in book.genres],
            offers=self._offers_for(book),
        )

    @staticmethod
    def _offers_for(book: Book) -> list[BookOffer]:
        """Resume os exemplares ativos em uma oferta por destino.

        O mesmo livro pode ter exemplares didáticos e comerciais ao mesmo
        tempo, então a vitrine mostra os dois selos. Para venda vale o menor
        preço; um destino sem exemplar livre vira "Esgotado" em vez de
        desaparecer (US02), e um exemplar de venda que está emprestado
        habilita a Reserva de Compra (RF07).
        """
        disponiveis: dict[DestinationType, bool] = {}
        emprestados: dict[DestinationType, bool] = {}
        precos: dict[DestinationType, Decimal | None] = {}

        for copy in book.copies:
            if not copy.is_active:
                continue
            destino = copy.destination
            disponiveis.setdefault(destino, False)
            emprestados.setdefault(destino, False)
            precos.setdefault(destino, None)

            if copy.status == CopyStatus.AVAILABLE:
                disponiveis[destino] = True
            elif copy.status in (CopyStatus.BORROWED, CopyStatus.RESERVED):
                emprestados[destino] = True

            # O preço vale mesmo com o exemplar indisponível: quem vê
            # "Esgotado" ainda quer saber por quanto sai quando voltar.
            if copy.sale_price is not None:
                atual = precos[destino]
                if atual is None or copy.sale_price < atual:
                    precos[destino] = copy.sale_price

        # Venda antes de empréstimo: é a informação com preço, que domina o
        # card na vitrine.
        ordem = (DestinationType.COMMERCIAL, DestinationType.DIDACTIC)
        ofertas = []
        for destino in ordem:
            if destino not in disponiveis:
                continue
            disponivel = disponiveis[destino]
            ofertas.append(
                BookOffer(
                    destination=destino,
                    available=disponivel,
                    price=precos[destino],
                    can_reserve=(
                        destino == DestinationType.COMMERCIAL
                        and not disponivel
                        and emprestados[destino]
                    ),
                )
            )
        return ofertas
