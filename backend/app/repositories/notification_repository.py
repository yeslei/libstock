from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.domain import Book, Notification, Profile, PurchaseReservation
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
