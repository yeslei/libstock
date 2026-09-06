from sqlalchemy.orm import Session

from app.models.domain import Book


class BookRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

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
