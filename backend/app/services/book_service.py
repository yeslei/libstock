from app.models.domain import Book
from app.repositories.book_repository import BookRepository


class BookService:
    def __init__(self, book_repository: BookRepository) -> None:
        self.book_repository = book_repository

    def search_books(self, title: str) -> list[Book]:
        normalized = title.strip()
        if not normalized:
            raise ValueError("O título da busca não pode estar vazio.")
        return self.book_repository.search_by_title(normalized)
