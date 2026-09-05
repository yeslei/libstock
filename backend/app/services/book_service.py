import httpx
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ApplicationError,
    BookPersistenceError,
    DuplicateIsbnError,
    EmployeeRecordRequiredError,
    GoogleBooksInvalidResponseError,
    GoogleBooksNotFoundError,
    GoogleBooksUnavailableError,
)
from app.models.domain import Book
from app.repositories.book_repository import BookRepository
from app.schemas.book_schema import BookCreate


GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
GOOGLE_BOOKS_TIMEOUT_SECONDS = 5.0


class BookService:
    def __init__(self, *, db: Session, repository: BookRepository) -> None:
        self.db = db
        self.repository = repository

    async def fetch_google_books_data(self, isbn: str) -> dict[str, str]:
        try:
            async with httpx.AsyncClient(timeout=GOOGLE_BOOKS_TIMEOUT_SECONDS) as client:
                response = await client.get(GOOGLE_BOOKS_URL, params={"q": f"isbn:{isbn}"})
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise GoogleBooksUnavailableError() from exc
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
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

    async def create_book(self, book_data: BookCreate, *, employee_id: int) -> Book:
        try:
            if not self.repository.employee_exists(employee_id):
                raise EmployeeRecordRequiredError()
            if self.repository.find_by_isbn(book_data.isbn) is not None:
                raise DuplicateIsbnError()

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
            self.db.commit()
            self.db.refresh(book)
            return book
        except IntegrityError as exc:
            self.db.rollback()
            raise DuplicateIsbnError() from exc
        except ApplicationError:
            self.db.rollback()
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BookPersistenceError() from exc
        except Exception as exc:
            self.db.rollback()
            raise BookPersistenceError() from exc
