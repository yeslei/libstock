from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.domain import (
    Book,
    BookGenre,
    Copy,
    CopyStatus,
    Employee,
    Genre,
    Loan,
    LoanStatus,
    Profile,
    PurchaseReservation,
    ReservationStatus,
)
from app.models.loan_request import LoanRequest
from app.models.user import User
from app.repositories.reservation_expiry import expire_due_reservations
from app.schemas.book_schema import BookCreate, BookUpdate, InitialCopyCreate


class BookRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def employee_exists(self, employee_id: int) -> bool:
        # Employee.id -> Profile.id -> User.id; as PKs/FKs compartilhadas, o ID
        # do usuário autenticado precisa existir exatamente em employees e o
        # funcionário (perfil e usuário) precisa estar ativo (Issue #151).
        return self.db.scalar(
            select(Employee.id)
            .join(Profile, Profile.id == Employee.id)
            .join(User, User.id == Employee.id)
            .where(
                Employee.id == employee_id,
                Profile.is_active.is_(True),
                User.is_active.is_(True),
            )
        ) is not None

    def find_by_id(self, book_id: int) -> Book | None:
        return self.db.get(Book, book_id)

    def find_by_isbn(self, isbn: str) -> Book | None:
        return self.db.scalar(select(Book).where(Book.isbn == isbn))

    def find_by_isbn_except(self, isbn: str, book_id: int) -> Book | None:
        return self.db.scalar(select(Book).where(Book.isbn == isbn, Book.id != book_id))

    def has_active_copy(self, book_id: int) -> bool:
        return self.db.scalar(
            select(Copy.id).where(Copy.book_id == book_id, Copy.is_active.is_(True)).limit(1)
        ) is not None

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

    def find_genres_by_ids(self, genre_ids: list[int]) -> list[Genre]:
        if not genre_ids:
            return []
        return list(self.db.scalars(select(Genre).where(Genre.id.in_(genre_ids))))

    def lock_book_row(self, book_id: int) -> None:
        """Serializa a sincronização de categorias da mesma obra (a chave de book_genres é composta)."""
        self.db.execute(select(Book.id).where(Book.id == book_id).with_for_update())

    def set_book_genres(self, book: Book, genres: list[Genre]) -> bool:
        """Faz book_genres refletir exatamente `genres`. Devolve se algo mudou (diferença mínima)."""
        wanted = {genre.id for genre in genres}
        current = set(self.db.scalars(select(BookGenre.genre_id).where(BookGenre.book_id == book.id)))
        removed, added = current - wanted, wanted - current
        if not removed and not added:
            return False
        if removed:
            self.db.execute(
                delete(BookGenre).where(BookGenre.book_id == book.id, BookGenre.genre_id.in_(removed))
            )
        for genre_id in sorted(added):
            self.db.add(BookGenre(book_id=book.id, genre_id=genre_id))
        self.db.flush()
        # A coleção `book.genres` já carregada na sessão ficou velha.
        self.db.expire(book, ["genres"])
        return True

    def create_book(self, book_data: BookCreate) -> Book:
        db_book = Book(**book_data.model_dump(exclude={"initial_copy", "genre_ids"}))
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

    def update_book(
        self,
        book: Book,
        changes: BookUpdate,
        *,
        genres: list[Genre] | None = None,
        genre_text: str | None = None,
    ) -> Book:
        # As categorias vão primeiro: o flush delas não deve emitir um UPDATE parcial de `books`,
        # para a auditoria registrar uma única alteração da obra.
        genres_changed = genres is not None and self.set_book_genres(book, genres)
        for field, value in changes.model_dump(exclude_unset=True, exclude={"genre_ids"}).items():
            setattr(book, field, value)
        if genres is not None:
            book.genre = genre_text
        if genres_changed:
            # A mudança só de categorias também precisa de um UPDATE em `books` para a auditoria.
            book.updated_at = func.now()
        self.db.flush()
        return book

    def search_by_title(self, title: str) -> list[Book]:
        escaped_title = (
            title.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        return (
            self.db.query(Book)
            .options(selectinload(Book.genres).selectinload(BookGenre.genre))
            .filter(
                Book.title.ilike(f"%{escaped_title}%", escape="\\"),
                Book.is_active.is_(True),
            )
            .all()
        )

    def lock_book_for_inactivation(self, book_id: int, now: datetime) -> Book | None:
        """Trava o livro, expira as reservas vencidas e trava os exemplares (livro, reservas, exemplares),
        serializando com empréstimos, vendas e destinações concorrentes."""
        book = self.db.scalar(
            select(Book)
            .where(Book.id == book_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if book is not None:
            expire_due_reservations(self.db, book_id, now)
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
