from datetime import datetime
import re

from sqlalchemy import and_, case, exists, false, func, or_, select
from sqlalchemy.orm import aliased
from app.models.domain import (
    Book, BookGenre, Client, Copy, CopyStatus, DestinationType, Genre, Loan, LoanStatus, Profile, PurchaseReservation, ReservationStatus,
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
            .order_by(func.lower(User.name), Client.id).limit(limit))
        if term:
            statement = statement.where(_matches(term, User.name, User.email))
        else:  # lista padrão (sem termo): somente clientes ativos
            statement = statement.where(Profile.is_active.is_(True), User.is_active.is_(True))
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

    def waiting_queues(self, book_ids, cutoff):
        """WAITING reservations of the books (full queues, not the filtered page) with client eligibility facts."""
        if not book_ids:
            return []
        statement = (select(PurchaseReservation.id.label('reservation_id'), PurchaseReservation.book_id.label('book_id'),
                            *self._client_columns(cutoff))
            .select_from(PurchaseReservation).join(Client, Client.id == PurchaseReservation.client_id)
            .join(Profile, Profile.id == Client.id).join(User, User.id == Client.id)
            .where(PurchaseReservation.book_id.in_(book_ids), PurchaseReservation.status == ReservationStatus.WAITING)
            .order_by(PurchaseReservation.book_id, PurchaseReservation.queue_position, PurchaseReservation.id))
        return self.db.execute(statement).mappings().all()

    def expired_notified_counts(self, book_ids, now):
        """Destinadas com prazo vencido ainda não efetivadas: o exemplar será liberado na próxima escrita da obra."""
        if not book_ids:
            return {}
        return dict(self.db.execute(select(PurchaseReservation.book_id, func.count()).where(
            PurchaseReservation.book_id.in_(book_ids), PurchaseReservation.status == ReservationStatus.NOTIFIED,
            PurchaseReservation.expires_at.is_not(None), PurchaseReservation.expires_at < now,
        ).group_by(PurchaseReservation.book_id)).all())

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
        return or_(_matches(term, Book.title, Book.author, Book.isbn, Book.genre), _matches_isbn(term, Book.isbn),
            select(BookGenre.book_id).join(Genre, Genre.id == BookGenre.genre_id).where(
                BookGenre.book_id == Book.id, _matches(term, Genre.name)).correlate(Book).exists(),
            select(Copy.id).where(Copy.book_id == Book.id, _matches(term, Copy.barcode)).correlate(Book).exists())

    @staticmethod
    def _availability_columns():
        free = free_copies_statement().with_only_columns(Copy.book_id, Copy.destination).subquery()
        def count(destination):
            return select(func.count()).select_from(free).where(free.c.book_id == Book.id,
                free.c.destination == destination).correlate(Book).scalar_subquery()
        return [count(DestinationType.DIDACTIC).label('available_didactic'),
                count(DestinationType.COMMERCIAL).label('available_commercial')]

    def catalog_books(self, term, limit, *, offset=0, availability="all"):
        """Obras com a contagem de exemplares ativos e não vendidos, por destinação."""
        counted = and_(Copy.is_active.is_(True), Copy.status != CopyStatus.SOLD)
        statement = (select(
                Book,
                func.count(case((counted, Copy.id))).label('total_copies'),
                func.count(case((and_(counted, Copy.destination == DestinationType.DIDACTIC), Copy.id))).label('didactic_copies'),
                func.count(case((and_(counted, Copy.destination == DestinationType.COMMERCIAL), Copy.id))).label('commercial_copies'),
                *self._availability_columns())
            .select_from(Book).outerjoin(Copy, Copy.book_id == Book.id).group_by(Book.id))
        if term:
            statement = statement.where(self._catalog_term(term))
        if availability == "inactive":
            statement = statement.where(Book.is_active.is_(False))
        elif availability != "all":
            didactic, commercial = self._availability_columns()
            condition = didactic > 0 if availability == "loan" else commercial > 0 if availability == "sale" else and_(didactic == 0, commercial == 0)
            statement = statement.where(Book.is_active.is_(True), condition)
        return self.db.execute(statement.order_by(func.lower(Book.title), Book.id).offset(offset).limit(limit)).mappings().all()

    def book_genres(self, book_ids):
        """Categorias do catálogo (book_genres) por obra, em ordem alfabética (Issue #174)."""
        if not book_ids:
            return {}
        rows = self.db.execute(
            select(BookGenre.book_id, Genre.id, Genre.name, Genre.slug)
            .join(Genre, Genre.id == BookGenre.genre_id)
            .where(BookGenre.book_id.in_(book_ids)).order_by(func.lower(Genre.name), Genre.id)).all()
        result = {}
        for book_id, genre_id, name, slug in rows:
            result.setdefault(book_id, []).append(dict(id=genre_id, name=name, slug=slug))
        return result

    def catalog_book(self, book_id):
        counted = and_(Copy.is_active.is_(True), Copy.status != CopyStatus.SOLD)
        statement = (select(
                Book,
                func.count(case((counted, Copy.id))).label('total_copies'),
                func.count(case((and_(counted, Copy.destination == DestinationType.DIDACTIC), Copy.id))).label('didactic_copies'),
                func.count(case((and_(counted, Copy.destination == DestinationType.COMMERCIAL), Copy.id))).label('commercial_copies'),
                *self._availability_columns())
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

    def copy_lookup(self, term, limit, destination=None, available=None):
        """Exemplares ativos por código, ISBN, título ou autor; `free` e estoque comercial livre pela definição comum."""
        free_ids = free_copies_statement().with_only_columns(Copy.id)
        statement = (select(Copy, Book, Copy.id.in_(free_ids).label('free'))
            .join(Book, Book.id == Copy.book_id).where(Copy.is_active.is_(True))
            .order_by(Book.title, Copy.id).limit(limit))
        if term:
            statement = statement.where(
                or_(_matches(term, Copy.barcode, Book.title, Book.author, Book.isbn), _matches_isbn(term, Book.isbn)))
        if destination is not None:
            statement = statement.where(Copy.destination == destination)
        if available is not None:
            statement = statement.where(Copy.id.in_(free_ids) if available else Copy.id.not_in(free_ids))
        return self.db.execute(statement).mappings().all()

    def dashboard_overview(self, cutoff, next_cutoff):
        """Histórico real; intervalos de calendário em America/Sao_Paulo, sem números de demonstração."""
        from datetime import timedelta
        start_week = cutoff - timedelta(days=6)
        start_month = cutoff - timedelta(days=29)
        local_date = lambda column: func.date(func.timezone('America/Sao_Paulo', column))
        loan_day = local_date(Loan.loan_date)
        return_day = local_date(Loan.returned_at)
        loan_counts = dict(self.db.execute(select(loan_day, func.count()).where(
            Loan.loan_date >= start_week, Loan.loan_date < next_cutoff, Loan.status != LoanStatus.CANCELLED
        ).group_by(loan_day)).all())
        return_counts = dict(self.db.execute(select(return_day, func.count()).where(
            Loan.returned_at >= start_week, Loan.returned_at < next_cutoff
        ).group_by(return_day)).all())
        category = func.coalesce(select(func.min(Genre.name)).join(BookGenre, BookGenre.genre_id == Genre.id)
            .where(BookGenre.book_id == Book.id).correlate(Book).scalar_subquery(), 'Outros')
        categories = [{'name': name, 'count': count} for name, count in self.db.execute(
            select(category, func.count(Book.id)).where(Book.is_active.is_(True)).group_by(category)
            .order_by(func.count(Book.id).desc(), category)).all()]
        reservations = select(func.count(PurchaseReservation.id)).where(PurchaseReservation.book_id == Book.id,
            PurchaseReservation.created_at >= start_month, PurchaseReservation.created_at < next_cutoff).correlate(Book).scalar_subquery()
        popular = [dict(row) for row in self.db.execute(select(Book.id, Book.title, Book.author, Book.cover_url,
            func.count(Loan.id).label('loans'), reservations.label('reservations')).join(Copy, Copy.book_id == Book.id)
            .join(Loan, Loan.copy_id == Copy.id).where(Loan.loan_date >= start_month, Loan.loan_date < next_cutoff,
                Loan.status != LoanStatus.CANCELLED).group_by(Book.id).order_by(func.count(Loan.id).desc(), Book.id).limit(5)).mappings()]
        def recent(returned):
            column = Loan.returned_at if returned else Loan.loan_date
            statement = select(Loan.id, Book.id.label('book_id'), Book.title, User.name.label('client'),
                Loan.loan_date.label('date'), Loan.due_date, Loan.returned_at, Loan.status).join(Copy, Copy.id == Loan.copy_id)
            statement = statement.join(Book, Book.id == Copy.book_id).join(User, User.id == Loan.client_id)
            statement = statement.where(Loan.returned_at.is_not(None) if returned else Loan.status != LoanStatus.CANCELLED)
            return [dict(row, status=row['status'].value) for row in self.db.execute(
                statement.order_by(column.desc(), Loan.id.desc()).limit(5)).mappings()]
        return {
            'loans_today': loan_counts.get(cutoff.date(), 0),
            'week': [{'date': (start_week + timedelta(days=i)).date(), 'loans': loan_counts.get((start_week + timedelta(days=i)).date(), 0),
                      'returns': return_counts.get((start_week + timedelta(days=i)).date(), 0)} for i in range(7)],
            'categories': categories, 'popular': popular, 'recent_loans': recent(False), 'recent_returns': recent(True),
        }
