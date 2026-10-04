from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.domain import (
    Book, Client, Copy, CopyStatus, DestinationType, Employee, Loan, LoanStatus, Profile, PurchaseReservation,
    ReservationStatus,
)
from app.models.user import User
from app.repositories.loan_rules import overdue_open_loan_clause
from app.repositories.reservation_expiry import expire_due_reservations


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

    def expire_due_reservations(self, book_id: int, now: datetime) -> int:
        return expire_due_reservations(self.db, book_id, now)

    def has_waiting_queue(self, book_id: int) -> bool:
        return self.db.scalar(select(PurchaseReservation.id).where(
            PurchaseReservation.book_id == book_id,
            PurchaseReservation.status == ReservationStatus.WAITING,
        ).limit(1)) is not None

    def has_queueable_commercial_copy(self, book_id: int) -> bool:
        """An active commercial copy that is not sold: a WAITING reservation can still be served."""
        return self.db.scalar(select(Copy.id).where(
            Copy.book_id == book_id, Copy.destination == DestinationType.COMMERCIAL, Copy.is_active.is_(True),
            Copy.status.in_([CopyStatus.AVAILABLE, CopyStatus.BORROWED, CopyStatus.RESERVED]),
        ).limit(1)) is not None

    def books_with_due_reservations(self, now: datetime) -> list[int]:
        return list(self.db.scalars(select(PurchaseReservation.book_id).where(
            PurchaseReservation.status == ReservationStatus.NOTIFIED,
            PurchaseReservation.expires_at.is_not(None), PurchaseReservation.expires_at < now,
        ).distinct().order_by(PurchaseReservation.book_id)))
