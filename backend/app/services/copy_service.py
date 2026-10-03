from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ApplicationError,
    AuditActorRequiredError,
    CopyDeletionBlockedError,
    CopyDeletionPersistenceError,
    CopyNotFoundError,
    EmployeeRecordRequiredError,
)
from app.models.domain import Book, CopyStatus
from app.repositories.copy_repository import CopyRepository
from app.schemas.copy_schema import CopyBatchCreate, CopyCreate, CopyDeleteResponse

LAST_ACTIVE_COPY_MESSAGE = "An active book requires at least one active copy"
FOREIGN_KEY_VIOLATION = "23503"
HISTORY_REASON = {
    "code": "copy_has_history",
    "message": "O exemplar possui histórico de empréstimo, venda, reserva ou solicitação.",
}
LAST_ACTIVE_REASON = {
    "code": "last_active_copy",
    "message": "É o último exemplar ativo de uma obra ativa.",
}

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

    def create_copies(
        self,
        copies_data: CopyBatchCreate,
        actor_id: int,
    ):
        if not self.repository.is_employee(actor_id):
            raise AuditActorRequiredError()

        try:
            self.repository.set_audit_actor(actor_id)

            book_id = copies_data.copies[0].book_id
            book = self.db.get(Book, book_id)

            if book is None or not book.is_active:
                raise HTTPException(
                    status_code=404,
                    detail="Obra não encontrada ou inativa.",
                )

            copies = self.repository.create_copies(copies_data.copies)

            self.db.commit()

            for copy in copies:
                self.db.refresh(copy)

            return copies

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
                detail="Não foi possível cadastrar os exemplares.",
            )

    def delete_copy(self, copy_id: int, actor_id: int) -> CopyDeleteResponse:
        """Exclui fisicamente um exemplar disponível e sem histórico (Issue #135)."""
        try:
            if not self.repository.is_active_employee(actor_id):
                raise EmployeeRecordRequiredError()
            self.repository.set_audit_actor(actor_id)

            copy = self.repository.find_copy(copy_id)
            if copy is None:
                raise CopyNotFoundError()
            # Livro antes do exemplar, como nos fluxos de circulação, para
            # serializar com empréstimo, venda e destinação concorrentes.
            book = self.repository.lock_book(copy.book_id)
            copy = self.repository.lock_copy(copy_id)
            if copy is None:
                raise CopyNotFoundError()

            reasons: list[dict] = []
            if copy.status != CopyStatus.AVAILABLE:
                reasons.append(
                    {
                        "code": "copy_not_available",
                        "message": f"O exemplar não está disponível (situação atual: {copy.status.value}).",
                    }
                )
            history = self.repository.history_counts(copy.id)
            if any(history.values()):
                reasons.append(HISTORY_REASON)
            if (
                book is not None
                and book.is_active
                and copy.is_active
                and not self.repository.has_other_active_copy(copy.book_id, copy.id)
            ):
                reasons.append(LAST_ACTIVE_REASON)
            if reasons:
                raise CopyDeletionBlockedError(reasons, history)

            response = CopyDeleteResponse(id=copy.id, book_id=copy.book_id, barcode=copy.barcode)
            self.repository.delete_copy(copy)
            self.db.commit()
            return response
        except ApplicationError:
            self.db.rollback()
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            # A integridade do banco é a última barreira: qualquer bloqueio não
            # previsto pela checagem acima continua sendo bloqueio, nunca 500.
            raise self._blocked_by_database(exc) from exc

    @staticmethod
    def _blocked_by_database(exc: SQLAlchemyError) -> ApplicationError:
        orig = getattr(exc, "orig", None)
        sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
        message = str(orig or exc)
        if LAST_ACTIVE_COPY_MESSAGE in message:
            return CopyDeletionBlockedError([LAST_ACTIVE_REASON], {})
        if isinstance(exc, IntegrityError) and (
            sqlstate == FOREIGN_KEY_VIOLATION or "foreign key" in message.lower()
        ):
            return CopyDeletionBlockedError([HISTORY_REASON], {})
        return CopyDeletionPersistenceError()
