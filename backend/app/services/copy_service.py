from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.domain import Book
from app.repositories.copy_repository import CopyRepository
from app.schemas.copy_schema import CopyCreate

class CopyService:
    def __init__(self, repository: CopyRepository, db: Session):
        self.repository = repository
        self.db = db

    def create_new_copy(self, copy_data: CopyCreate):
        book = self.db.get(Book, copy_data.book_id)
        if book is None or not book.is_active:
            raise HTTPException(status_code=404, detail="Obra não encontrada ou inativa.")

        try:
            return self.repository.create_copy(copy_data=copy_data)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Já existe um exemplar com este código de barras.",
            ) from exc