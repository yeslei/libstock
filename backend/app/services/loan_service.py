from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.loan_repository import LoanRepository
from app.services.client_pendency_service import ClientPendencyService
from app.schemas.loan_schema import LoanCreate, LoanResponse
from app.models.domain import CopyStatus, LoanStatus


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

            copy = self.repository.find_copy_for_loan(loan_data.copy_id)

            if copy is None:
                raise HTTPException(
                    status_code=404,
                    detail="Exemplar não encontrado ou inativo.",
                )

            if copy.status != CopyStatus.AVAILABLE:
                raise HTTPException(
                    status_code=409,
                    detail="Exemplar não está disponível para empréstimo.",
                )

            loan = self.repository.create_loan(
                loan_data,
                employee_id=employee_id,
            )

            self.db.commit()
            self.db.refresh(loan)

            return LoanResponse.model_validate(loan)

        except HTTPException:
            self.db.rollback()
            raise

        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail=(
                    "Não foi possível registrar o empréstimo porque "
                    "o exemplar já possui um empréstimo em aberto."
                ),
            ) from exc

        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Não foi possível registrar o empréstimo.",
            ) from exc

    def register_return(
        self,
        loan_id: int,
    ) -> LoanResponse:
        try:
            loan = self.repository.find_loan_for_return(loan_id)

            if loan is None:
                raise HTTPException(
                    status_code=404,
                    detail="Empréstimo não encontrado.",
                )

            if loan.status != LoanStatus.OPEN:
                raise HTTPException(
                    status_code=409,
                    detail="Empréstimo não está aberto para devolução.",
                )

            copy = self.repository.find_copy_for_return(loan.copy_id)

            if copy is None:
                raise HTTPException(
                    status_code=404,
                    detail="Exemplar vinculado ao empréstimo não encontrado.",
                )

            returned_at = datetime.now(timezone.utc)

            loan = self.repository.register_return(
                loan,
                copy,
                returned_at=returned_at,
            )

            self.db.commit()
            self.db.refresh(loan)

            return LoanResponse.model_validate(loan)

        except HTTPException:
            self.db.rollback()
            raise

        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Não foi possível registrar a devolução.",
            ) from exc

        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Não foi possível registrar a devolução.",
            ) from exc