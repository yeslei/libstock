from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.domain import Book, Client, Loan, LoanStatus, Profile
from app.models.user import User


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
            Loan.client_id == client_id, Loan.status == LoanStatus.OPEN, Loan.due_date < cutoff,
        ).limit(1)) is not None
