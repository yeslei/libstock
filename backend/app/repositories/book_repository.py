from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.domain import (
    Book,
    Copy,
    CopyStatus,
    Employee,
    Loan,
    LoanStatus,
    PurchaseReservation,
    ReservationStatus,
)
from app.models.loan_request import LoanRequest
from app.models.user import User
from app.schemas.book_schema import BookCreate, BookUpdate, InitialCopyCreate


class BookRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def employee_exists(self, employee_id: int) -> bool:
        # Employee.id -> Profile.id -> User.id; as PKs/FKs compartilhadas, o ID
        # do usuário autenticado precisa existir exatamente em employees.
        return self.db.get(Employee, employee_id) is not None

    def find_by_id(self, book_id: int) -> Book | None:
        return self.db.get(Book, book_id)

    def find_by_isbn(self, isbn: str) -> Book | None:
        return self.db.scalar(select(Book).where(Book.isbn == isbn))

    def find_by_isbn_except(self, isbn: str, book_id: int) -> Book | None:
        return self.db.scalar(select(Book).where(Book.isbn == isbn, Book.id != book_id))

    def get_with_copies(self, book_id: int) -> Book | None:
        return self.db.scalar(
            select(Book).options(selectinload(Book.copies)).where(Book.id == book_id)
        )

    def get_book_availability(self, book_id: int) -> tuple[Book, int] | None:
        statement = (
            select(Book, func.count(Copy.id))
            .outerjoin(
                Copy,
                (Copy.book_id == Book.id)
                & Copy.is_active.is_(True)
                & (Copy.status == CopyStatus.AVAILABLE),
            )
            .where(Book.id == book_id, Book.is_active.is_(True))
            .group_by(Book.id)
        )
        row = self.db.execute(statement).one_or_none()
        if row is None:
            return None
        book, available_copies_count = row
        return book, int(available_copies_count)
    def find_copy_by_barcode(self, barcode: str) -> Copy | None:
        return self.db.scalar(select(Copy).where(Copy.barcode == barcode))

    def create_book(self, book_data: BookCreate) -> Book:
        db_book = Book(**book_data.model_dump(exclude={"initial_copy"}))
        self.db.add(db_book)
        self.db.flush()
        return db_book

    def create_copy(self, book_id: int, copy_data: InitialCopyCreate) -> Copy:
        db_copy = Copy(
            book_id=book_id,
            status=CopyStatus.AVAILABLE,
            is_active=True,
            **copy_data.model_dump(),
        )
        self.db.add(db_copy)
        self.db.flush()
        return db_copy

    def update_book(self, book: Book, changes: BookUpdate) -> Book:
        for field, value in changes.model_dump(exclude_unset=True).items():
            setattr(book, field, value)
        self.db.flush()
        return book

    def search_by_title(self, title: str) -> list[Book]:
        escaped_title = (
            title.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        return (
            self.db.query(Book)
            .filter(
                Book.title.ilike(f"%{escaped_title}%", escape="\\"),
                Book.is_active.is_(True),
            )
            .all()
        )

    def lock_book_for_inactivation(self, book_id: int) -> Book | None:
        """Trava o livro e seus exemplares, serializando com empréstimos e vendas concorrentes."""
        book = self.db.scalar(
            select(Book)
            .where(Book.id == book_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        self.db.execute(
            select(Copy.id).where(Copy.book_id == book_id).order_by(Copy.id).with_for_update()
        )
        return book

    def active_operation_counts(self, book_id: int) -> dict[str, int]:
        return {
            "open_loans": self.db.scalar(
                select(func.count())
                .select_from(Loan)
                .join(Copy, Copy.id == Loan.copy_id)
                .where(Copy.book_id == book_id, Loan.status == LoanStatus.OPEN)
            ),
            "pending_loan_requests": self.db.scalar(
                select(func.count())
                .select_from(LoanRequest)
                .where(LoanRequest.book_id == book_id, LoanRequest.loan_id.is_(None))
            ),
            "purchase_reservations": self.db.scalar(
                select(func.count())
                .select_from(PurchaseReservation)
                .where(
                    PurchaseReservation.book_id == book_id,
                    PurchaseReservation.status.in_(
                        [ReservationStatus.WAITING, ReservationStatus.NOTIFIED]
                    ),
                )
            ),
        }

    def active_operation_links(
        self, book_id: int, limit: int = 10, *, include_clients: bool = False
    ) -> list[dict]:
        """Vínculos legíveis (código do exemplar e cliente) para a tela de bloqueio."""
        links: list[dict] = []
        loans = self.db.execute(
            select(Copy.barcode, User.name)
            .select_from(Loan)
            .join(Copy, Copy.id == Loan.copy_id)
            .join(User, User.id == Loan.client_id)
            .where(Copy.book_id == book_id, Loan.status == LoanStatus.OPEN)
            .order_by(Loan.id)
            .limit(limit)
        )
        links += [
            {"type": "open_loan", "copy_barcode": barcode, "client_name": name}
            for barcode, name in loans
        ]
        requests = self.db.execute(
            select(User.name)
            .select_from(LoanRequest)
            .join(User, User.id == LoanRequest.client_id)
            .where(LoanRequest.book_id == book_id, LoanRequest.loan_id.is_(None))
            .order_by(LoanRequest.id)
            .limit(limit)
        )
        links += [
            {"type": "pending_loan_request", "copy_barcode": None, "client_name": name}
            for (name,) in requests
        ]
        reservations = self.db.execute(
            select(Copy.barcode, User.name)
            .select_from(PurchaseReservation)
            .join(User, User.id == PurchaseReservation.client_id)
            .outerjoin(Copy, Copy.id == PurchaseReservation.allocated_copy_id)
            .where(
                PurchaseReservation.book_id == book_id,
                PurchaseReservation.status.in_(
                    [ReservationStatus.WAITING, ReservationStatus.NOTIFIED]
                ),
            )
            .order_by(PurchaseReservation.id)
            .limit(limit)
        )
        links += [
            {"type": "purchase_reservation", "copy_barcode": barcode, "client_name": name}
            for barcode, name in reservations
        ]
        if not include_clients:
            for link in links:
                link.pop("client_name")
        return links
