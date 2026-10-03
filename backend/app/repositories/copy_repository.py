from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session
from app.models.domain import (
    Book,
    Copy,
    Employee,
    Loan,
    Profile,
    PurchaseReservation,
    SaleItem,
)
from app.models.loan_request import LoanRequest
from app.models.purchase_request import PurchaseRequest
from app.models.user import User
from app.schemas.copy_schema import CopyCreate

class CopyRepository:
    def __init__(self, db: Session):
        self.db = db

    def is_employee(self, user_id: int) -> bool:
        return self.db.scalar(select(Employee.id).where(Employee.id == user_id)) is not None

    def set_audit_actor(self, employee_id: int) -> None:
        self.db.execute(
            text("SELECT set_config('libstock.employee_id', :valor, true)"),
            {"valor": str(employee_id)},
        )

    def create_copy(self, copy_data: CopyCreate) -> Copy:
        db_copy = Copy(
            book_id=copy_data.book_id,
            barcode=copy_data.barcode,
            destination=copy_data.destination,
            condition=copy_data.condition,
            sale_price=copy_data.sale_price,
            acquired_at=copy_data.acquired_at,
        )
        self.db.add(db_copy)
        self.db.flush()
        self.db.refresh(db_copy)
        return db_copy

    def create_copies(self, copies_data: list[CopyCreate]) -> list[Copy]:
        db_copies = [
            Copy(
                book_id=copy_data.book_id,
                barcode=copy_data.barcode,
                destination=copy_data.destination,
                condition=copy_data.condition,
                sale_price=copy_data.sale_price,
                acquired_at=copy_data.acquired_at,
            )
            for copy_data in copies_data
        ]

        self.db.add_all(db_copies)
        self.db.flush()

        for db_copy in db_copies:
            self.db.refresh(db_copy)

        return db_copies

    def is_active_employee(self, user_id: int) -> bool:
        return self.db.scalar(
            select(Employee.id)
            .join(Profile, Profile.id == Employee.id)
            .join(User, User.id == Employee.id)
            .where(
                Employee.id == user_id,
                Profile.is_active.is_(True),
                User.is_active.is_(True),
            )
        ) is not None

    def find_copy(self, copy_id: int) -> Copy | None:
        return self.db.get(Copy, copy_id)

    def lock_book(self, book_id: int) -> Book | None:
        # Mesmo lock de linha do livro usado pelos fluxos de circulação.
        return self.db.scalar(
            select(Book)
            .where(Book.id == book_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def lock_copy(self, copy_id: int) -> Copy | None:
        return self.db.scalar(
            select(Copy)
            .where(Copy.id == copy_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def history_counts(self, copy_id: int) -> dict[str, int]:
        """Vínculos que impedem a exclusão física do exemplar."""
        reservation_match = or_(
            PurchaseReservation.allocated_copy_id == copy_id,
            PurchaseReservation.fulfilled_copy_id == copy_id,
        )
        loan_requests = self.db.scalar(
            select(func.count())
            .select_from(LoanRequest)
            .join(Loan, Loan.id == LoanRequest.loan_id)
            .where(Loan.copy_id == copy_id)
        )
        purchase_requests = self.db.scalar(
            select(func.count())
            .select_from(PurchaseRequest)
            .join(PurchaseReservation, PurchaseReservation.id == PurchaseRequest.reservation_id)
            .where(reservation_match)
        )
        return {
            "loans": self.db.scalar(
                select(func.count()).select_from(Loan).where(Loan.copy_id == copy_id)
            ),
            "sales": self.db.scalar(
                select(func.count()).select_from(SaleItem).where(SaleItem.copy_id == copy_id)
            ),
            "purchase_reservations": self.db.scalar(
                select(func.count()).select_from(PurchaseReservation).where(reservation_match)
            ),
            "requests": loan_requests + purchase_requests,
        }

    def has_other_active_copy(self, book_id: int, copy_id: int) -> bool:
        return self.db.scalar(
            select(Copy.id)
            .where(Copy.book_id == book_id, Copy.id != copy_id, Copy.is_active.is_(True))
            .limit(1)
        ) is not None

    def delete_copy(self, copy: Copy) -> None:
        self.db.delete(copy)
        self.db.flush()
