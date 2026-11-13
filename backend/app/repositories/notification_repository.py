from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.domain import (
    Book, Copy, Loan, Notification, NotificationChannel, NotificationStatus,
    Profile, PurchaseReservation,
)
from app.models.user import User


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def availability_data(self, reservation_id: int):
        return self.db.execute(select(PurchaseReservation, Book, Profile, User)
            .join(Book, Book.id == PurchaseReservation.book_id)
            .join(Profile, Profile.id == PurchaseReservation.client_id)
            .join(User, User.id == Profile.id)
            .where(PurchaseReservation.id == reservation_id)
            .execution_options(populate_existing=True)).first()

    def return_reminder_data(self, loan_id: int):
        return self.db.execute(
            select(Loan, Book, Profile, User)
            .join(Copy, Copy.id == Loan.copy_id)
            .join(Book, Book.id == Copy.book_id)
            .join(Profile, Profile.id == Loan.client_id)
            .join(User, User.id == Loan.client_id)
            .where(Loan.id == loan_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()

    def create_return_reminder(self, *, user_id: int, channel, subject: str, message: str,
                               status, sent_at):
        item = Notification(
            user_id=user_id,
            reservation_id=None,
            type="RETURN_REMINDER",
            channel=channel,
            subject=subject,
            message=message,
            status=status,
            sent_at=sent_at,
        )
        self.db.add(item)
        self.db.flush()
        return item

    def enqueue(self, **values) -> None:
        # A reserva já foi serializada pelo lock da obra. O índice protege
        # também chamadas repetidas e escritores fora do fluxo normal.
        self.db.execute(insert(Notification).values(**values).on_conflict_do_nothing(
            index_elements=[Notification.type, Notification.reservation_id],
            index_where=Notification.reservation_id.is_not(None),
        ))

    def list_own(self, user_id: int, *, before_id: int | None, limit: int):
        query = select(Notification).where(Notification.user_id == user_id)
        if before_id is not None:
            query = query.where(Notification.id < before_id)
        return self.db.scalars(query.order_by(Notification.id.desc()).limit(limit)).all()

    def lock_own(self, notification_id: int, user_id: int):
        return self.db.scalar(select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id,
        ).with_for_update().execution_options(populate_existing=True))

    def pending_candidates(self, limit: int):
        return self.db.execute(select(Notification.id, PurchaseReservation.book_id, Notification.reservation_id)
            .join(PurchaseReservation, PurchaseReservation.id == Notification.reservation_id)
            .where(Notification.status == NotificationStatus.PENDING,
                   Notification.channel == NotificationChannel.EMAIL,
                   Notification.type == "RESERVATION_AVAILABLE")
            .order_by(Notification.id).limit(limit)).all()

    def lock_book_for_dispatch(self, book_id: int):
        return self.db.scalar(select(Book).where(Book.id == book_id)
            .with_for_update(skip_locked=True).execution_options(populate_existing=True))

    def lock_reservation_for_dispatch(self, reservation_id: int):
        return self.db.scalar(select(PurchaseReservation).where(PurchaseReservation.id == reservation_id)
            .with_for_update().execution_options(populate_existing=True))

    def lock_for_dispatch(self, notification_id: int):
        return self.db.scalar(select(Notification).where(Notification.id == notification_id,
            Notification.status == NotificationStatus.PENDING, Notification.channel == NotificationChannel.EMAIL,
        ).with_for_update(skip_locked=True).execution_options(populate_existing=True))

    def confirm_sent(self, notification_id: int, now) -> None:
        item = self.db.scalar(select(Notification).where(Notification.id == notification_id)
            .with_for_update().execution_options(populate_existing=True))
        if item is not None and item.status == NotificationStatus.FAILED:
            item.status = NotificationStatus.SENT
            item.sent_at = now
