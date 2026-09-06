from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AuditActorRequiredError
from app.models.domain import Book
from app.repositories.copy_repository import CopyRepository
from app.schemas.copy_schema import CopyCreate

class CopyService:
    def __init__(self, repository: CopyRepository, db: Session):
        self.repository = repository
        self.db = db

    def create_new_copy(self, copy_data: CopyCreate, actor_id: int):
        if not self.repository.is_employee(actor_id):
            raise AuditActorRequiredError()

        try:
            self.repository.set_audit_actor(actor_id)

            book = self.db.get(Book, copy_data.book_id)
            if book is None or not book.is_active:
                raise HTTPException(status_code=404, detail="Obra não encontrada ou inativa.")

            copy = self.repository.create_copy(copy_data=copy_data)
            self.db.commit()
            self.db.refresh(copy)
            return copy
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Já existe um exemplar com este código de barras.",
            ) from exc
        except HTTPException:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Não foi possível cadastrar o exemplar.",
            )
