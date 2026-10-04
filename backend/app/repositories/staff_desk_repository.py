from datetime import datetime
import re

from sqlalchemy import and_, case, exists, false, func, or_, select
from sqlalchemy.orm import aliased
from app.models.domain import (
    Book, Client, Copy, CopyStatus, DestinationType, Loan, LoanStatus, Profile, PurchaseReservation, ReservationStatus,
)
from app.models.loan_request import LoanRequest
from app.models.purchase_request import PurchaseRequest
from app.models.user import User
from app.repositories.client_request_repository import ClientRequestRepository
from app.repositories.inventory_availability import free_copies_statement
from app.repositories.loan_rules import overdue_open_loan_clause


def _contains(value: str) -> str:
    escaped = value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return f'%{escaped}%'


def _matches(term: str, *columns):
    pattern = _contains(term)
    return or_(*[column.ilike(pattern, escape='\\') for column in columns])


def _matches_isbn(term: str, isbn_column):
    """O ISBN é gravado compacto; o termo pode vir com hífens ou espaços."""
    compact = re.sub(r'[\s-]', '', term)
    return _matches(compact, isbn_column) if compact else false()


class StaffDeskRepository(ClientRequestRepository):
    """Consultas somente leitura do balcão. Devolve fatos; a elegibilidade é decidida no service."""

    @classmethod
    def _client_columns(cls, cutoff: datetime):
        late = aliased(Loan)
        overdue = exists().where(late.client_id == Client.id, overdue_open_loan_clause(cutoff, late)).label('has_overdue_loan')
        return (Client.id.label('client_id'), User.name.label('client_name'), User.email.label('client_email'),
                Profile.is_active.label('profile_active'), User.is_active.label('user_active'),
                Client.is_penalized.label('client_penalized'), overdue)

    @staticmethod
    def _filtered(statement, term, client_id, *extra_columns, isbn=None):
        if client_id is not None:
            statement = statement.where(Client.id == client_id)
        if term:
            conditions = [_matches(term, User.name, User.email, Book.title, Book.author, *extra_columns)]
            if isbn is not None:
                conditions.append(_matches_isbn(term, isbn))
            statement = statement.where(or_(*conditions))
        return statement

    def search_clients(self, term, cutoff, limit):
        statement = (select(*self._client_columns(cutoff)).select_from(Client)
            .join(Profile, Profile.id == Client.id).join(User, User.id == Client.id)
            .where(_matches(term, User.name, User.email)).order_by(User.name, Client.id).limit(limit))
        return self.db.execute(statement).mappings().all()

    def client_summary(self, client_id, cutoff):
        statement = (select(*self._client_columns(cutoff)).select_from(Client)
            .join(Profile, Profile.id == Client.id).join(User, User.id == Client.id).where(Client.id == client_id))
        return self.db.execute(statement).mappings().first()

    def pending_loan_requests(self, term, client_id, cutoff, limit):
        statement = (select(LoanRequest, Book, *self._client_columns(cutoff)).select_from(LoanRequest)
            .join(Book, Book.id == LoanRequest.book_id).join(Client, Client.id == LoanRequest.client_id)
            .join(Profile, Profile.id == Client.id).join(User, User.id == Client.id)
            .where(LoanRequest.loan_id.is_(None)))
        statement = self._filtered(statement, term, client_id)
        return self.db.execute(statement.order_by(LoanRequest.pickup_date, LoanRequest.id).limit(limit)).mappings().all()

    def eligible_didactic_copies(self, book_ids):
        """Mesma definição de exemplar livre usada por lock_free_copy na confirmação da retirada."""
        if not book_ids:
            return []
        return list(self.db.scalars(free_copies_statement().where(
            Copy.book_id.in_(book_ids), Copy.destination == DestinationType.DIDACTIC,
        ).order_by(Copy.book_id, Copy.id)))

    def open_loans(self, term, client_id, cutoff, limit):
        statement = (select(Loan, Copy, Book, *self._client_columns(cutoff)).select_from(Loan)
            .join(Copy, Copy.id == Loan.copy_id).join(Book, Book.id == Copy.book_id)
            .join(Client, Client.id == Loan.client_id).join(Profile, Profile.id == Client.id)
            .join(User, User.id == Client.id).where(Loan.status == LoanStatus.OPEN))
        statement = self._filtered(statement, term, client_id, Copy.barcode, Book.isbn, isbn=Book.isbn)
        return self.db.execute(statement.order_by(Loan.due_date, Loan.id).limit(limit)).mappings().all()

    def active_reservations(self, term, client_id, status, cutoff, limit):
        allocated = aliased(Copy)
        earlier = aliased(PurchaseReservation)
        position = (select(func.count()).where(
            earlier.book_id == PurchaseReservation.book_id, earlier.status == ReservationStatus.WAITING,
            earlier.queue_position < PurchaseReservation.queue_position,
        ).scalar_subquery() + 1).label('waiting_position')
        statuses = [status] if status else [ReservationStatus.WAITING, ReservationStatus.NOTIFIED]
        statement = (select(PurchaseReservation, Book, allocated.barcode.label('allocated_barcode'),
                PurchaseRequest.pickup_date.label('pickup_date'), position, *self._client_columns(cutoff))
            .select_from(PurchaseReservation)
            .join(Book, Book.id == PurchaseReservation.book_id).join(Client, Client.id == PurchaseReservation.client_id)
            .join(Profile, Profile.id == Client.id).join(User, User.id == Client.id)
            .outerjoin(allocated, allocated.id == PurchaseReservation.allocated_copy_id)
            .outerjoin(PurchaseRequest, PurchaseRequest.reservation_id == PurchaseReservation.id)
            .where(PurchaseReservation.status.in_(statuses)))
        statement = self._filtered(statement, term, client_id, allocated.barcode)
        return self.db.execute(statement.order_by(
            Book.title, PurchaseReservation.book_id, PurchaseReservation.queue_position, PurchaseReservation.id,
        ).limit(limit)).mappings().all()

    def free_commercial_counts(self, book_ids):
        if not book_ids:
            return {}
        free = free_copies_statement().where(
            Copy.book_id.in_(book_ids), Copy.destination == DestinationType.COMMERCIAL).subquery()
        return dict(self.db.execute(select(free.c.book_id, func.count()).group_by(free.c.book_id)).all())

    def dashboard_counts(self, cutoff: datetime, next_cutoff: datetime):
        """Indicadores do painel; cutoff/next_cutoff delimitam o dia de negócio atual (America/Sao_Paulo)."""
        def scalar(statement):
            return self.db.scalar(statement) or 0
        return {
            'active_loans': scalar(select(func.count()).select_from(Loan).where(Loan.status == LoanStatus.OPEN)),
            'returns_today': scalar(select(func.count()).select_from(Loan).where(
                Loan.returned_at >= cutoff, Loan.returned_at < next_cutoff)),
            'waiting_reservations': scalar(select(func.count()).select_from(PurchaseReservation).where(
                PurchaseReservation.status == ReservationStatus.WAITING)),
            'pendencies': scalar(select(func.count(func.distinct(Loan.client_id))).where(
                overdue_open_loan_clause(cutoff))),
        }


    @staticmethod
    def _catalog_term(term):
        return or_(_matches(term, Book.title, Book.author, Book.isbn), _matches_isbn(term, Book.isbn))

    def catalog_books(self, term, limit):
        """Obras com a contagem de exemplares ativos e não vendidos, por destinação."""
        counted = and_(Copy.is_active.is_(True), Copy.status != CopyStatus.SOLD)
        statement = (select(
                Book,
                func.count(case((counted, Copy.id))).label('total_copies'),
                func.count(case((and_(counted, Copy.destination == DestinationType.DIDACTIC), Copy.id))).label('didactic_copies'),
                func.count(case((and_(counted, Copy.destination == DestinationType.COMMERCIAL), Copy.id))).label('commercial_copies'))
            .select_from(Book).outerjoin(Copy, Copy.book_id == Book.id).group_by(Book.id))
        if term:
            statement = statement.where(self._catalog_term(term))
        return self.db.execute(statement.order_by(Book.title, Book.id).limit(limit)).mappings().all()

    def catalog_book(self, book_id):
        counted = and_(Copy.is_active.is_(True), Copy.status != CopyStatus.SOLD)
        statement = (select(
                Book,
                func.count(case((counted, Copy.id))).label('total_copies'),
                func.count(case((and_(counted, Copy.destination == DestinationType.DIDACTIC), Copy.id))).label('didactic_copies'),
                func.count(case((and_(counted, Copy.destination == DestinationType.COMMERCIAL), Copy.id))).label('commercial_copies'))
            .select_from(Book).outerjoin(Copy, Copy.book_id == Book.id).where(Book.id == book_id).group_by(Book.id))
        return self.db.execute(statement).mappings().first()

    def book_copies(self, book_id):
        """Exemplares da obra com `free` (mesma definição de exemplar livre) e a marca de destinação a reserva."""
        free_ids = free_copies_statement(book_id).with_only_columns(Copy.id)
        allocated = exists().where(PurchaseReservation.allocated_copy_id == Copy.id,
                                   PurchaseReservation.status == ReservationStatus.NOTIFIED)
        statement = (select(Copy, Copy.id.in_(free_ids).label('free'), allocated.label('allocated_for_purchase'))
            .where(Copy.book_id == book_id).order_by(Copy.id))
        return self.db.execute(statement).mappings().all()

    def copy_lookup(self, term, limit):
        """Exemplares ativos por código, ISBN, título ou autor; `free` e estoque comercial livre pela definição comum."""
        free_ids = free_copies_statement().with_only_columns(Copy.id)
        statement = (select(Copy, Book, Copy.id.in_(free_ids).label('free'))
            .join(Book, Book.id == Copy.book_id).where(Copy.is_active.is_(True))
            .where(or_(_matches(term, Copy.barcode, Book.title, Book.author, Book.isbn), _matches_isbn(term, Book.isbn)))
            .order_by(Book.title, Copy.id).limit(limit))
        return self.db.execute(statement).mappings().all()
