from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ApplicationError,
    AuditActorRequiredError,
    CopyDeletionBlockedError,
    CopyDeletionPersistenceError,
    CopyNotFoundError,
    CopySalePriceNotAllowedError,
    CopySalePriceRequiredError,
    CopyUpdateBlockedError,
    CopyUpdatePersistenceError,
    EmployeeRecordRequiredError,
    PermissionDeniedError,
)
from decimal import Decimal

from app.models.domain import Book, CopyStatus, DestinationType
from app.repositories.copy_repository import CopyRepository
from app.schemas.copy_schema import CopyBatchCreate, CopyCreate, CopyDeleteResponse, CopyUpdate

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

INACTIVE_REASON = {
    "code": "copy_inactive",
    "message": "O exemplar está inativo.",
}
ALLOCATED_REASON = {
    "code": "copy_allocated",
    "message": "O exemplar está destinado a uma reserva de compra.",
}
OPERATION_REASON = {
    "code": "copy_in_operation",
    "message": "O exemplar está em uma venda em andamento.",
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

    def update_copy(self, copy_id: int, changes: CopyUpdate, actor_id: int):
        """Edita ou converte exemplar disponível, ativo e sem operação em andamento (Issue #151)."""
        try:
            if not self.repository.is_active_employee(actor_id):
                raise EmployeeRecordRequiredError()
            self.repository.set_audit_actor(actor_id)

            copy = self.repository.find_copy(copy_id)
            if copy is None:
                raise CopyNotFoundError()
            # Livro antes do exemplar, como nos fluxos de circulação, para
            # serializar com empréstimo, venda e destinação concorrentes.
            self.repository.lock_book(copy.book_id)
            copy = self.repository.lock_copy(copy_id)
            if copy is None:
                raise CopyNotFoundError()

            reasons: list[dict] = []
            if not copy.is_active:
                reasons.append(INACTIVE_REASON)
            if copy.status != CopyStatus.AVAILABLE:
                reasons.append(
                    {
                        "code": "copy_not_available",
                        "message": f"O exemplar não está disponível (situação atual: {copy.status.value}).",
                    }
                )
            if self.repository.is_allocated_to_reservation(copy.id):
                reasons.append(ALLOCATED_REASON)
            if self.repository.has_open_sale(copy.id):
                reasons.append(OPERATION_REASON)
            if reasons:
                raise CopyUpdateBlockedError(reasons)

            values = self._resolve_update(copy, changes)
            if values:
                self.repository.apply_copy_changes(copy, values)
            self.db.commit()
            self.db.refresh(copy)
            return copy
        except ApplicationError:
            self.db.rollback()
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise self._update_failure(exc) from exc

    @staticmethod
    def _resolve_update(copy, changes: CopyUpdate) -> dict:
        fields = changes.model_fields_set
        destination = changes.destination if "destination" in fields else copy.destination
        values: dict = {}
        if destination == DestinationType.COMMERCIAL:
            price = changes.sale_price if "sale_price" in fields else copy.sale_price
            if price is None or Decimal(price) <= 0:
                raise CopySalePriceRequiredError()
            values["sale_price"] = price
        else:
            if copy.destination == DestinationType.DIDACTIC and changes.sale_price is not None:
                raise CopySalePriceNotAllowedError()
            values["sale_price"] = None
        values["destination"] = destination
        if "condition" in fields:
            values["condition"] = changes.condition
        if "acquired_at" in fields:
            values["acquired_at"] = changes.acquired_at
        return {key: value for key, value in values.items() if getattr(copy, key) != value}

    @staticmethod
    def _update_failure(exc: SQLAlchemyError) -> ApplicationError:
        message = str(getattr(exc, "orig", None) or exc)
        if "allocated copy" in message.lower():
            return CopyUpdateBlockedError([ALLOCATED_REASON])
        if "can change destination" in message:
            return CopyUpdateBlockedError(
                [{"code": "copy_not_available", "message": "O exemplar não está disponível para conversão."}]
            )
        if "Changing destination requires" in message:
            return PermissionDeniedError()
        if "chk_commercial_price" in message:
            return CopySalePriceRequiredError()
        if "chk_didactic_without_sale_price" in message:
            return CopySalePriceNotAllowedError()
        return CopyUpdatePersistenceError()

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
