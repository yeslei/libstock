from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Book, Client, Copy, Profile, PurchaseReservation, ReservationStatus, Sale, SaleItem, SaleStatus
from app.models.user import User
from app.repositories.reservation_expiry import expire_due_reservations


class SaleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_client(self, client_id: int) -> Client | None:
        return self.db.scalar(
            select(Client).where(Client.id == client_id)
        )

    def client_active_state(self, client_id: int) -> bool | None:
        """None se o cliente não existe; True só com perfil e usuário ativos."""
        row = self.db.execute(
            select(Profile.is_active, User.is_active)
            .select_from(Client)
            .join(Profile, Profile.id == Client.id)
            .join(User, User.id == Client.id)
            .where(Client.id == client_id)
        ).first()
        return None if row is None else bool(row[0] and row[1])

    def lock_books_for_copies(self, copy_ids: list[int]) -> dict[int, Book]:
        """Trava os livros dos exemplares, em ordem de id, antes de travar os exemplares."""
        book_ids = select(Copy.book_id).where(Copy.id.in_(copy_ids))
        books = self.db.scalars(
            select(Book)
            .where(Book.id.in_(book_ids))
            .order_by(Book.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).all()
        return {book.id: book for book in books}

    def expire_due_reservations(self, book_ids, now: datetime) -> None:
        """Com os livros travados, efetiva a expiração das reservas vencidas (livro, depois reservas)."""
        for book_id in sorted(book_ids):
            expire_due_reservations(self.db, book_id, now)

    def reserved_copy_ids(self, copy_ids: list[int]) -> set[int]:
        """Exemplares ainda destinados a reserva NOTIFIED (as vencidas já foram expiradas)."""
        return set(self.db.scalars(
            select(PurchaseReservation.allocated_copy_id).where(
                PurchaseReservation.allocated_copy_id.in_(copy_ids),
                PurchaseReservation.status == ReservationStatus.NOTIFIED,
            )
        ))

    def find_copies_for_sale(self, copy_ids: list[int]) -> list[Copy]:
        statement = (
            select(Copy)
            .where(Copy.id.in_(copy_ids))
            .with_for_update()
        )

        return list(self.db.scalars(statement).all())

    def create_sale(
        self,
        *,
        client_id: int,
        employee_id: int,
        total_amount: Decimal,
    ) -> Sale:
        sale = Sale(
            client_id=client_id,
            employee_id=employee_id,
            total_amount=total_amount,
        )

        self.db.add(sale)
        self.db.flush()

        return sale

    def create_sale_items(
        self,
        *,
        sale_id: int,
        items: list[tuple[int, Decimal]],
    ) -> list[SaleItem]:
        sale_items = [
            SaleItem(
                sale_id=sale_id,
                copy_id=copy_id,
                unit_price=unit_price,
            )
            for copy_id, unit_price in items
        ]

        self.db.add_all(sale_items)
        self.db.flush()

        return sale_items

    def confirm_sale(self, sale: Sale) -> None:
        """PENDING -> CONFIRMED; os gatilhos do banco aplicam SOLD aos exemplares."""
        sale.status = SaleStatus.CONFIRMED
        self.db.flush()
