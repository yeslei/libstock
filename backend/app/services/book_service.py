import logging
import re
from datetime import datetime

import httpx
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.business_dates import BUSINESS_ZONE
from app.core.config import Settings, get_settings
from app.core.exceptions import (
    ApplicationError,
    BookHasActiveOperationsError,
    BookPersistenceError,
    BookUpdatePersistenceError,
    DuplicateBarcodeError,
    DuplicateIsbnError,
    EmployeeRecordRequiredError,
    GenreNotFoundError,
    GenreTextWithGenreIdsError,
    GoogleBooksInvalidResponseError,
    GoogleBooksNotFoundError,
    GoogleBooksRateLimitError,
    GoogleBooksUnavailableError,
    BookNotFoundError,
    BookWithoutActiveCopyError,
)
from app.models.domain import Book, Genre
from app.repositories.book_repository import BookRepository
from app.services.copy_rules import require_commercial_price
from app.schemas.book_schema import (
    BookAvailabilityResponse,
    BookCreate,
    BookDetailResponse,
    BookMetadataResponse,
    BookResponse,
    BookUpdate,
    CopyResponse,
    normalize_isbn,
)


GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
GOOGLE_BOOKS_TIMEOUT_SECONDS = 5.0
logger = logging.getLogger(__name__)
LAST_ACTIVE_COPY_MESSAGE = "An active book requires at least one active copy"
GENRE_TEXT_MAX_LENGTH = 100
GENRE_FK_CONSTRAINT = "book_genres_genre_id_fkey"


def _is_genre_fk_violation(exc: IntegrityError) -> bool:
    """Categoria removida entre a leitura e o commit: vira 404 `genre_not_found`, nunca 500."""
    constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    return constraint == GENRE_FK_CONSTRAINT or GENRE_FK_CONSTRAINT in str(exc.orig)

UNIQUE_CONSTRAINT_ERRORS = {
    "books_isbn_key": DuplicateIsbnError,
    "copies_barcode_key": DuplicateBarcodeError,
}


def _unique_constraint_name(exc: IntegrityError) -> str | None:
    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint_name in UNIQUE_CONSTRAINT_ERRORS:
        return constraint_name

    message = str(exc.orig)
    for known_name in UNIQUE_CONSTRAINT_ERRORS:
        if re.search(
            rf"(?:duplicate key[^\n]*violates\s+unique\s+constraint|unique\s+constraint\s+failed:)\s*[\"']?{re.escape(known_name)}[\"']?",
            message,
            flags=re.IGNORECASE,
        ):
            return known_name
    return None


class BookService:
    def __init__(
        self,
        book_repository: BookRepository | None = None,
        *,
        db: Session | None = None,
        repository: BookRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.repository = repository or book_repository
        if self.repository is None:
            raise TypeError("BookRepository é obrigatório.")
        self.db = db or self.repository.db
        self.settings = settings or get_settings()

    async def fetch_google_books_data(self, isbn: str) -> dict[str, str]:
        """Consulta o Google Books. Só devolve sugestões; quem decide é o chamador."""
        try:
            async with httpx.AsyncClient(timeout=GOOGLE_BOOKS_TIMEOUT_SECONDS) as client:
                params = {"q": f"isbn:{isbn}"}
                if self.settings.google_books_api_key:
                    params["key"] = self.settings.google_books_api_key
                response = await client.get(GOOGLE_BOOKS_URL, params=params)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise GoogleBooksUnavailableError() from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise GoogleBooksRateLimitError() from exc
            raise GoogleBooksUnavailableError() from exc
        except httpx.RequestError as exc:
            raise GoogleBooksUnavailableError() from exc

        try:
            data = response.json()
        except (TypeError, ValueError) as exc:
            raise GoogleBooksInvalidResponseError() from exc

        if not isinstance(data, dict) or data.get("totalItems", 0) == 0:
            raise GoogleBooksNotFoundError()

        items = data.get("items")
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            raise GoogleBooksInvalidResponseError()
        volume_info = items[0].get("volumeInfo")
        if not isinstance(volume_info, dict):
            raise GoogleBooksInvalidResponseError()

        external_data: dict[str, str] = {}
        title = volume_info.get("title")
        if isinstance(title, str) and title.strip():
            external_data["title"] = title.strip()

        authors = volume_info.get("authors")
        if isinstance(authors, list):
            valid_authors = [
                author.strip()
                for author in authors
                if isinstance(author, str) and author.strip()
            ]
            if valid_authors:
                external_data["author"] = ", ".join(valid_authors)

        categories = volume_info.get("categories")
        if isinstance(categories, list):
            genre = next(
                (
                    category.strip()
                    for category in categories
                    if isinstance(category, str) and category.strip()
                ),
                None,
            )
            if genre:
                external_data["genre"] = genre

        publisher = volume_info.get("publisher")
        if isinstance(publisher, str) and publisher.strip():
            external_data["publisher"] = publisher.strip()[:150]

        published_date = volume_info.get("publishedDate")
        if isinstance(published_date, str):
            year_match = re.match(r"\s*(\d{4})", published_date)
            if year_match and 1000 <= int(year_match.group(1)) <= 2100:
                external_data["publication_year"] = year_match.group(1)

        image_links = volume_info.get("imageLinks")
        if isinstance(image_links, dict):
            for key in ("thumbnail", "smallThumbnail"):
                link = image_links.get(key)
                if isinstance(link, str) and link.strip():
                    cover = link.strip().replace("http://", "https://", 1)
                    if cover.startswith("https://") and len(cover) <= 2048:
                        external_data["cover_url"] = cover
                        break
        return external_data

    async def lookup_metadata(self, isbn: str) -> BookMetadataResponse:
        normalized_isbn = normalize_isbn(isbn)
        external_data = await self.fetch_google_books_data(normalized_isbn)
        if not external_data.get("title") or not external_data.get("author"):
            raise GoogleBooksInvalidResponseError()
        try:
            return BookMetadataResponse(
                isbn=normalized_isbn,
                title=external_data["title"],
                author=external_data["author"],
                genre=external_data.get("genre"),
                cover_url=external_data.get("cover_url"),
                publisher=external_data.get("publisher"),
                publication_year=(
                    int(external_data["publication_year"])
                    if external_data.get("publication_year")
                    else None
                ),
            )
        except ValidationError as exc:
            raise GoogleBooksInvalidResponseError() from exc

    # Campos que a consulta externa pode preencher quando o funcionário os deixou vazios.
    # Categorias nunca vêm da consulta externa (Issue #176): o vocabulário do Google Books
    # não é o do acervo.
    _EXTERNAL_FILL_FIELDS = ("title", "author", "cover_url", "publisher", "publication_year")

    async def _complete_with_external_data(self, book_data: BookCreate) -> BookCreate:
        """Os dados informados prevalecem; o Google Books só preenche campos vazios (Issue #176)."""
        empty = [
            field
            for field in self._EXTERNAL_FILL_FIELDS
            if getattr(book_data, field) is None
        ]
        if not empty:
            return book_data
        try:
            external = await self.fetch_google_books_data(book_data.isbn)
        except (
            GoogleBooksNotFoundError,
            GoogleBooksUnavailableError,
            GoogleBooksRateLimitError,
            GoogleBooksInvalidResponseError,
        ):
            # Sem a base externa, o cadastro manual continua valendo se tiver título e autor.
            if not book_data.title or not book_data.author:
                raise
            return book_data

        merged = book_data.model_dump()
        for field in empty:
            value = external.get(field)
            if value:
                merged[field] = int(value) if field == "publication_year" else value
        try:
            return BookCreate.model_validate(merged)
        except ValidationError as exc:
            if not book_data.title or not book_data.author:
                raise GoogleBooksInvalidResponseError() from exc
            return book_data

    def _resolve_genres(self, genre_ids: list[int]) -> list[Genre]:
        """Categorias do catálogo para os ids informados; qualquer id inexistente é 404 estável (Issue #174)."""
        genres = self.repository.find_genres_by_ids(genre_ids)
        found = {genre.id for genre in genres}
        missing = [genre_id for genre_id in genre_ids if genre_id not in found]
        if missing:
            raise GenreNotFoundError(missing)
        by_id = {genre.id: genre for genre in genres}
        return [by_id[genre_id] for genre_id in genre_ids]

    @staticmethod
    def genre_text(genres: list[Genre]) -> str | None:
        """Texto legado `books.genre`: nomes das categorias separados por vírgula, até 100 caracteres."""
        text_value = ""
        for genre in genres:
            candidate = f"{text_value}, {genre.name}" if text_value else genre.name
            if len(candidate) > GENRE_TEXT_MAX_LENGTH:
                break
            text_value = candidate
        return text_value or None

    async def create_book(self, book_data: BookCreate, *, employee_id: int) -> BookResponse:
        try:
            if not self.repository.employee_exists(employee_id):
                raise EmployeeRecordRequiredError()
            require_commercial_price(
                book_data.initial_copy.destination, book_data.initial_copy.sale_price
            )
            if book_data.genre_ids is not None and book_data.genre is not None:
                raise GenreTextWithGenreIdsError()
            if self.repository.find_by_isbn(book_data.isbn) is not None:
                raise DuplicateIsbnError()
            if self.repository.find_copy_by_barcode(book_data.initial_copy.barcode) is not None:
                raise DuplicateBarcodeError()

            genres = (
                self._resolve_genres(book_data.genre_ids)
                if book_data.genre_ids is not None
                else None
            )
            persisted_data = await self._complete_with_external_data(book_data)
            if genres is not None:
                # As categorias escolhidas valem; o texto legado só espelha os nomes.
                persisted_data = persisted_data.model_copy(update={"genre": self.genre_text(genres)})

            if not persisted_data.title or not persisted_data.author:
                raise GoogleBooksInvalidResponseError()

            self.db.execute(
                text(
                    "SELECT set_config("
                    "'libstock.employee_id', :employee_id, true"
                    ")"
                ),
                {"employee_id": str(employee_id)},
            )
            book = self.repository.create_book(persisted_data)
            if genres:
                self.repository.set_book_genres(book, genres)
            initial_copy = self.repository.create_copy(book.id, persisted_data.initial_copy)
            response = BookResponse(
                id=book.id,
                isbn=book.isbn,
                title=book.title,
                author=book.author,
                genre=book.genre,
                cover_url=book.cover_url,
                is_active=book.is_active,
                genres=list(genres or []),
                initial_copy=CopyResponse.model_validate(initial_copy),
            )
            self.db.commit()
            return response
        except IntegrityError as exc:
            self.db.rollback()
            constraint = _unique_constraint_name(exc)
            if constraint is not None:
                raise UNIQUE_CONSTRAINT_ERRORS[constraint]() from exc
            if _is_genre_fk_violation(exc):
                raise GenreNotFoundError() from exc
            logger.exception("Falha de integridade inesperada ao cadastrar obra e exemplar")
            raise BookPersistenceError() from exc
        except ApplicationError:
            self.db.rollback()
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.exception("Falha de persistência ao cadastrar obra e exemplar")
            raise BookPersistenceError() from exc
        except Exception as exc:
            self.db.rollback()
            logger.exception("Falha inesperada ao cadastrar obra e exemplar")
            raise BookPersistenceError() from exc

    def search_books(self, title: str) -> list[Book]:
        normalized = title.strip()
        if not normalized:
            raise ValueError("O título da busca não pode estar vazio.")
        return self.repository.search_by_title(normalized)

    def get_book_availability(self, book_id: int) -> BookAvailabilityResponse:
        result = self.repository.get_book_availability(book_id)
        if result is None:
            raise BookNotFoundError()
        book, available_copies_count = result
        return BookAvailabilityResponse(
            id=book.id,
            title=book.title,
            is_available=available_copies_count > 0,
            available_copies_count=available_copies_count,
        )
    def get_book(self, book_id: int) -> BookDetailResponse:
        book = self.repository.get_with_copies(book_id)
        if book is None:
            raise BookNotFoundError()
        return BookDetailResponse.model_validate(book)

    def update_book(
        self,
        book_id: int,
        changes: BookUpdate,
        *,
        employee_id: int,
        can_view_clients: bool = False,
    ) -> BookDetailResponse:
        try:
            if not self.repository.employee_exists(employee_id):
                raise EmployeeRecordRequiredError()
            book = self.repository.get_with_copies(book_id)
            if book is None:
                raise BookNotFoundError()
            if changes.isbn is not None and self.repository.find_by_isbn_except(
                changes.isbn, book_id
            ) is not None:
                raise DuplicateIsbnError()
            if "genre_ids" in changes.model_fields_set and "genre" in changes.model_fields_set:
                raise GenreTextWithGenreIdsError()
            self.db.execute(
                text("SELECT set_config('libstock.employee_id', :employee_id, true)"),
                {"employee_id": str(employee_id)},
            )
            if changes.is_active is not None:
                # Trava a obra e os exemplares antes de decidir o ramo, usando o valor
                # travado: duas mudanças de situação concorrentes não decidem sobre dado velho.
                self.repository.lock_book_for_inactivation(book_id, datetime.now(BUSINESS_ZONE))
                if changes.is_active is False and book.is_active:
                    self._ensure_no_active_operations(book_id, can_view_clients)
                elif changes.is_active is True and not book.is_active:
                    self._ensure_has_active_copy(book_id)
            genres = None
            if "genre_ids" in changes.model_fields_set:
                # Ordem: obra (e exemplares) primeiro, depois as categorias com FOR SHARE, que impede
                # a remoção concorrente de uma categoria até o commit desta transação.
                self.repository.lock_book_row(book_id)
                genres = self._resolve_genres(changes.genre_ids)
            genre_args = (
                {"genres": genres, "genre_text": self.genre_text(genres)}
                if genres is not None
                else {}
            )
            updated = self.repository.update_book(book, changes, **genre_args)
            response = BookDetailResponse.model_validate(updated)
            self.db.commit()
            return response
        except IntegrityError as exc:
            self.db.rollback()
            if _unique_constraint_name(exc) == "books_isbn_key":
                raise DuplicateIsbnError() from exc
            if _is_genre_fk_violation(exc):
                raise GenreNotFoundError() from exc
            raise BookUpdatePersistenceError() from exc
        except ApplicationError:
            self.db.rollback()
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            # O gatilho adiado trg_active_book_has_copy é a última barreira da reativação.
            diag = getattr(getattr(exc, "orig", None), "diag", None)
            if getattr(diag, "message_primary", None) == LAST_ACTIVE_COPY_MESSAGE:
                raise BookWithoutActiveCopyError() from exc
            raise BookUpdatePersistenceError() from exc

    def _ensure_has_active_copy(self, book_id: int) -> None:
        """Reativação exige ao menos um exemplar ativo (decisão 7 de #147, Issue #151)."""
        # O livro e os exemplares já estão travados em update_book: nenhum exemplar é
        # excluído ou inativado entre a conferência e o commit.
        if not self.repository.has_active_copy(book_id):
            raise BookWithoutActiveCopyError()

    def _ensure_no_active_operations(self, book_id: int, can_view_clients: bool) -> None:
        """Bloqueia a inativação enquanto houver operação em andamento (Issue #135)."""
        # Com o livro e os exemplares travados (em update_book), nenhuma retirada, empréstimo ou
        # destinação concorrente confirma entre a contagem e o commit.
        counts = self.repository.active_operation_counts(book_id)
        if any(counts.values()):
            raise BookHasActiveOperationsError(
                counts, self.repository.active_operation_links(book_id, include_clients=can_view_clients)
            )
