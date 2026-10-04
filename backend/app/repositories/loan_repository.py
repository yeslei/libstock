from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Book, Copy, CopyStatus, Loan, LoanStatus
from app.schemas.loan_schema import LoanCreate


class LoanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def lock_book_for_copy(self, copy_id: int) -> Book | None:
        """Trava o livro do exemplar antes do exemplar (ordem livro -> exemplar dos demais fluxos)."""
        book_id = self.db.scalar(select(Copy.book_id).where(Copy.id == copy_id))
        if book_id is None:
            return None
        return self.db.scalar(
            select(Book)
            .where(Book.id == book_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

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
        loan_date: datetime,
        due_date: datetime,
    ) -> Loan:
        loan = Loan(
            client_id=loan_data.client_id,
            copy_id=loan_data.copy_id,
            employee_id=employee_id,
            loan_date=loan_date,
            due_date=due_date,
        )
        self.db.add(loan)
        self.db.flush()
        return loan

    def find_loan_for_return(self, loan_id: int) -> Loan | None:
        return self.db.scalar(
            select(Loan)
            .where(Loan.id == loan_id)
            .with_for_update()
        )

    def find_copy_for_return(self, copy_id: int) -> Copy | None:
        return self.db.scalar(
            select(Copy)
            .where(Copy.id == copy_id)
            .with_for_update()
        )

    def register_return(
        self,
        loan: Loan,
        copy: Copy,
        *,
        returned_at: datetime,
    ) -> Loan:
        loan.returned_at = returned_at
        loan.status = LoanStatus.RETURNED
        copy.status = CopyStatus.AVAILABLE

        self.db.flush()

        return loan