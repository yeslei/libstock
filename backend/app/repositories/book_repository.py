from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Book, Employee
from app.schemas.book_schema import BookCreate

class BookRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def employee_exists(self, employee_id: int) -> bool:
        # Employee.id -> Profile.id -> User.id; as PKs/FKs compartilhadas, o ID
        # do usuário autenticado precisa existir exatamente em employees.
        return self.db.get(Employee, employee_id) is not None

    def find_by_isbn(self, isbn: str) -> Book | None:
        return self.db.scalar(select(Book).where(Book.isbn == isbn))

    def create_book(self, book_data: BookCreate) -> Book:
        db_book = Book(**book_data.model_dump())
        self.db.add(db_book)
        self.db.flush()
        return db_book

    def search_by_title(self, title: str) -> list[Book]:
        escaped_title = (
            title.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        return (
            self.db.query(Book)
            .filter(
                Book.title.ilike(f"%{escaped_title}%", escape="\\"),
                Book.is_active.is_(True),
            )
            .all()
        )
