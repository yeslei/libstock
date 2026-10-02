from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.domain import CopyStatus
from app.repositories.loan_repository import LoanRepository
from app.schemas.loan_schema import LoanCreate, LoanResponse
from app.services.client_pendency_service import ClientPendencyService


LOAN_DURATION_DAYS = 15


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
            # Valida situação do cliente e bloqueia cliente com pendências.
            self.client_pendency_service.validate_client_for_operation(
                loan_data.client_id,
                commit=False,
            )

            # Busca o exemplar com lock para evitar concorrência.
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

            # Regra de negócio: empréstimos possuem prazo de 15 dias corridos.
            loan_date = datetime.now(timezone.utc)
            due_date = loan_date + timedelta(days=LOAN_DURATION_DAYS)

            loan = self.repository.create_loan(
                loan_data,
                employee_id=employee_id,
                loan_date=loan_date,
                due_date=due_date,
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