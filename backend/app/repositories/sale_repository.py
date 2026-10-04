from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Book, Client, Copy, Sale, SaleItem, SaleStatus


class SaleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_client(self, client_id: int) -> Client | None:
        return self.db.scalar(
            select(Client).where(Client.id == client_id)
        )

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
        client_id: int | None,
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
