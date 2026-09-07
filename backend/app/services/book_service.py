import logging
import re

import httpx
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ApplicationError,
    BookPersistenceError,
    DuplicateBarcodeError,
    DuplicateIsbnError,
    EmployeeRecordRequiredError,
    GoogleBooksInvalidResponseError,
    GoogleBooksNotFoundError,
    GoogleBooksRateLimitError,
    GoogleBooksUnavailableError,
)
from app.models.domain import Book
from app.repositories.book_repository import BookRepository
from app.schemas.book_schema import BookCreate, BookResponse, CopyResponse


GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
GOOGLE_BOOKS_TIMEOUT_SECONDS = 5.0
logger = logging.getLogger(__name__)

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
    ) -> None:
        self.repository = repository or book_repository
        if self.repository is None:
            raise TypeError("BookRepository é obrigatório.")
        self.db = db or self.repository.db

    async def fetch_google_books_data(self, isbn: str) -> dict[str, str]:
        try:
            async with httpx.AsyncClient(timeout=GOOGLE_BOOKS_TIMEOUT_SECONDS) as client:
                response = await client.get(GOOGLE_BOOKS_URL, params={"q": f"isbn:{isbn}"})
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
        return external_data

    async def create_book(self, book_data: BookCreate, *, employee_id: int) -> BookResponse:
        try:
            if not self.repository.employee_exists(employee_id):
                raise EmployeeRecordRequiredError()
            if self.repository.find_by_isbn(book_data.isbn) is not None:
                raise DuplicateIsbnError()
            if self.repository.find_copy_by_barcode(book_data.initial_copy.barcode) is not None:
                raise DuplicateBarcodeError()

            persisted_data = book_data
            if not book_data.title or not book_data.author:
                external_data = await self.fetch_google_books_data(book_data.isbn)
                merged_data = book_data.model_dump()
                for field_name in ("title", "author", "genre"):
                    if not merged_data[field_name] and external_data.get(field_name):
                        merged_data[field_name] = external_data[field_name]
                try:
                    persisted_data = BookCreate.model_validate(merged_data)
                except ValidationError as exc:
                    raise GoogleBooksInvalidResponseError() from exc

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
            initial_copy = self.repository.create_copy(book.id, persisted_data.initial_copy)
            response = BookResponse(
                id=book.id,
                isbn=book.isbn,
                title=book.title,
                author=book.author,
                genre=book.genre,
                is_active=book.is_active,
                initial_copy=CopyResponse.model_validate(initial_copy),
            )
            self.db.commit()
            return response
        except IntegrityError as exc:
            self.db.rollback()
            constraint = _unique_constraint_name(exc)
            if constraint is not None:
                raise UNIQUE_CONSTRAINT_ERRORS[constraint]() from exc
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
