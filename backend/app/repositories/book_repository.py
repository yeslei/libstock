from sqlalchemy.orm import Session
from app.models.domain import Book
from app.schemas.book_schema import BookCreate

class BookRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_book(self, book_data: BookCreate) -> Book:
        db_book = Book(
            isbn=book_data.isbn,
            title=book_data.title,
            author=book_data.author,
            genre=book_data.genre,
            publication_year=book_data.publication_year,
            publisher=book_data.publisher,
            edition=book_data.edition,
            cover_url=book_data.cover_url,
        )
        self.db.add(db_book)
        self.db.commit()
        self.db.refresh(db_book)
        return db_book