from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Copy, CopyStatus, Loan
from app.schemas.loan_schema import LoanCreate


class LoanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_copy_for_loan(self, copy_id: int) -> Copy | None:
        return self.db.scalar(
            select(Copy)
            .where(
                Copy.id == copy_id,
                Copy.is_active.is_(True),
            )
            .with_for_update()
        )

    def create_loan(
        self,
        loan_data: LoanCreate,
        *,
        employee_id: int,
    ) -> Loan:
        loan = Loan(
            client_id=loan_data.client_id,
            copy_id=loan_data.copy_id,
            employee_id=employee_id,
            due_date=loan_data.due_date,
        )
        self.db.add(loan)
        self.db.flush()
        return loan