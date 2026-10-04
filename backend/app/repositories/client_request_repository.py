from datetime import datetime
from sqlalchemy import and_, select
from sqlalchemy.orm import Session
from app.models.domain import Book, Client, Employee, Loan, LoanStatus, Profile
from app.models.user import User


def overdue_open_loan_clause(cutoff: datetime):
    """Single overdue predicate (business-day cutoff) shared by every flow."""
    return and_(Loan.status == LoanStatus.OPEN, Loan.returned_at.is_(None), Loan.due_date < cutoff)


class ClientRequestRepository:
    """Shared persistence operations; no loan-specific inheritance for purchases."""
    def __init__(self, db: Session):
        self.db = db

    def lock_client(self, client_id: int):
        return self.db.execute(
            select(Client, Profile, User).join(Profile, Profile.id == Client.id)
            .join(User, User.id == Client.id).where(Client.id == client_id).with_for_update()
        ).first()

    def lock_book(self, book_id: int):
        return self.db.scalar(select(Book).where(Book.id == book_id).with_for_update())

    def has_overdue_loan(self, client_id: int, cutoff: datetime) -> bool:
        return self.db.scalar(select(Loan.id).where(
            Loan.client_id == client_id, overdue_open_loan_clause(cutoff),
        ).limit(1)) is not None

    def is_active_employee(self, actor_id):
        return self.db.scalar(select(Employee.id).join(Profile, Profile.id == Employee.id)
            .join(User, User.id == Employee.id).where(
                Employee.id == actor_id, Profile.is_active.is_(True), User.is_active.is_(True),
            )) is not None
