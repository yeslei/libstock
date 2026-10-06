from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Client, Copy, Sale, SaleItem


class SaleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_client(self, client_id: int) -> Client | None:
        return self.db.scalar(
            select(Client).where(Client.id == client_id)
        )

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
        items,
    ) -> list[SaleItem]:
        sale_items = [
            SaleItem(
                sale_id=sale_id,
                copy_id=item.copy_id,
                unit_price=item.unit_price,
            )
            for item in items
        ]

        self.db.add_all(sale_items)
        self.db.flush()

        return sale_items