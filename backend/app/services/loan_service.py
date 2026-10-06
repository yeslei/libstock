from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.business_dates import loan_due_at
from app.core.exceptions import (
    ApplicationError,
    BookInactiveError,
    CopyNotAvailableError,
    CopyNotFoundError,
    CopyNotForLoanError,
    LoanConflictError,
    LoanNotFoundError,
    LoanNotOpenError,
    LoanPersistenceError,
    LoanReturnConflictError,
    LoanReturnPersistenceError,
)
from app.models.domain import CopyStatus, DestinationType, LoanStatus
from app.repositories.loan_repository import LoanRepository
from app.schemas.loan_schema import LoanCreate, LoanResponse
from app.services.client_pendency_service import ClientPendencyService


class LoanService:
    def __init__(
        self,
        repository: LoanRepository,
        db: Session,
        client_pendency_service: ClientPendencyService,
    ) -> None:
        self.repository = repository
        self.db = db
        self.client_pendency_service = client_pendency_service

    def create_loan(
        self,
        loan_data: LoanCreate,
        *,
        employee_id: int,
    ) -> LoanResponse:
        try:
            self.client_pendency_service.validate_client_for_operation(
                loan_data.client_id,
                commit=False,
            )

            book = self.repository.lock_book_for_copy(loan_data.copy_id)
            copy = self.repository.find_copy_for_loan(loan_data.copy_id)

            if copy is None:
                raise CopyNotFoundError("Exemplar não encontrado ou inativo.")

            if book is None or not book.is_active:
                raise BookInactiveError()

            if copy.status != CopyStatus.AVAILABLE:
                raise CopyNotAvailableError("Exemplar não está disponível para empréstimo.")

            if copy.destination != DestinationType.DIDACTIC:
                raise CopyNotForLoanError()

            # Regra aprovada: vence um mês de calendário depois (America/Sao_Paulo).
            loan_date = datetime.now(timezone.utc)
            due_date = loan_due_at(loan_date)

            loan = self.repository.create_loan(
                loan_data,
                employee_id=employee_id,
                loan_date=loan_date,
                due_date=due_date,
            )

            self.db.commit()
            self.db.refresh(loan)

            return LoanResponse.model_validate(loan)

        except ApplicationError:
            self.db.rollback()
            raise

        except IntegrityError as exc:
            self.db.rollback()
            raise LoanConflictError() from exc

        except SQLAlchemyError as exc:
            self.db.rollback()
            raise LoanPersistenceError() from exc

    def register_return(
        self,
        loan_id: int,
    ) -> LoanResponse:
        try:
            loan = self.repository.find_loan_for_return(loan_id)

            if loan is None:
                raise LoanNotFoundError()

            if loan.status != LoanStatus.OPEN:
                raise LoanNotOpenError()

            copy = self.repository.find_copy_for_return(loan.copy_id)

            if copy is None:
                raise CopyNotFoundError("Exemplar vinculado ao empréstimo não encontrado.")

            returned_at = datetime.now(timezone.utc)

            loan = self.repository.register_return(
                loan,
                copy,
                returned_at=returned_at,
            )

            self.db.commit()
            self.db.refresh(loan)

            return LoanResponse.model_validate(loan)

        except ApplicationError:
            self.db.rollback()
            raise

        except IntegrityError as exc:
            self.db.rollback()
            raise LoanReturnConflictError() from exc

        except SQLAlchemyError as exc:
            self.db.rollback()
            raise LoanReturnPersistenceError() from exc