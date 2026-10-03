from datetime import datetime, time
from sqlalchemy.exc import SQLAlchemyError
from app.core.business_dates import BUSINESS_ZONE as ZONE, business_today
from app.core.exceptions import ApplicationError
from app.models.domain import ReservationStatus
from app.repositories.staff_desk_repository import StaffDeskRepository
from app.schemas.staff_desk_schema import (
    EligibleCopy, StaffBook, StaffClient, StaffLoan, StaffLoanRequest, StaffPurchaseReservation,
)
from app.services.client_eligibility import is_client_eligible

MIN_SEARCH_LENGTH = 2


class StaffDeskService:
    """Consultas de balcão: somente leitura, sempre por funcionário ativo."""

    def __init__(self, db, repository: StaffDeskRepository):
        self.db = db
        self.repository = repository

    def _guard(self, actor_id):
        if not self.repository.is_active_employee(actor_id):
            raise ApplicationError('Cadastro de funcionário ativo necessário.', 'employee_record_required', 403)
        today = business_today()
        return today, datetime.combine(today, time.min, ZONE)

    def _read(self, query):
        try:
            return query()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ApplicationError('Não foi possível consultar o balcão.', 'desk_query_error', 500) from exc

    @staticmethod
    def _term(term):
        term = (term or '').strip()
        return term or None

    @staticmethod
    def _client(row):
        has_overdue = bool(row['has_overdue_loan'])
        return StaffClient(
            id=row['client_id'], name=row['client_name'], email=row['client_email'],
            is_active=bool(row['profile_active'] and row['user_active']),
            is_penalized=row['client_penalized'], has_overdue_loan=has_overdue,
            eligible=is_client_eligible(profile_active=row['profile_active'], user_active=row['user_active'],
                                        penalized=row['client_penalized'], has_overdue=has_overdue))

    @staticmethod
    def _book(book):
        return StaffBook(id=book.id, title=book.title, author=book.author, is_active=book.is_active)

    def search_clients(self, term, actor_id, limit):
        term = self._term(term)
        if term is None or len(term) < MIN_SEARCH_LENGTH:
            raise ApplicationError(f'Informe ao menos {MIN_SEARCH_LENGTH} caracteres para buscar clientes.',
                                   'search_term_too_short', 422)
        _, cutoff = self._guard(actor_id)
        return [self._client(row) for row in self._read(lambda: self.repository.search_clients(term, cutoff, limit))]

    def loan_requests(self, actor_id, term, client_id, limit):
        _, cutoff = self._guard(actor_id)
        rows = self._read(lambda: self.repository.pending_loan_requests(self._term(term), client_id, cutoff, limit))
        copies = {}
        active_books = {row['Book'].id for row in rows if row['Book'].is_active}
        for copy in self._read(lambda: self.repository.eligible_didactic_copies(sorted(active_books))):
            copies.setdefault(copy.book_id, []).append(EligibleCopy(id=copy.id, barcode=copy.barcode, condition=copy.condition))
        return [StaffLoanRequest(
            id=row['LoanRequest'].id, client=self._client(row), book=self._book(row['Book']),
            pickup_date=row['LoanRequest'].pickup_date, due_date=row['LoanRequest'].due_date,
            created_at=row['LoanRequest'].created_at, eligible_copies=copies.get(row['Book'].id, []),
        ) for row in rows]

    def loans(self, actor_id, term, client_id, limit):
        today, cutoff = self._guard(actor_id)
        result = []
        for row in self._read(lambda: self.repository.open_loans(self._term(term), client_id, cutoff, limit)):
            loan, copy = row['Loan'], row['Copy']
            late = max(0, (today - loan.due_date.astimezone(ZONE).date()).days)
            result.append(StaffLoan(
                id=loan.id, client=self._client(row), book=self._book(row['Book']), copy_id=copy.id,
                copy_barcode=copy.barcode, loan_date=loan.loan_date, due_date=loan.due_date,
                status='OVERDUE' if late else 'ACTIVE', days_late=late))
        return result

    def purchase_reservations(self, actor_id, term, client_id, status, limit):
        _, cutoff = self._guard(actor_id)
        rows = self._read(lambda: self.repository.active_reservations(
            self._term(term), client_id, ReservationStatus(status) if status else None, cutoff, limit))
        free = self._read(lambda: self.repository.free_commercial_counts(sorted({row['Book'].id for row in rows})))
        now = datetime.now(ZONE)
        result = []
        for row in rows:
            reservation, book, client = row['PurchaseReservation'], row['Book'], self._client(row)
            waiting = reservation.status == ReservationStatus.WAITING
            position = row['waiting_position'] if waiting else None
            available = free.get(book.id, 0)
            blocked = None
            if waiting:
                if not book.is_active:
                    blocked = 'BOOK_INACTIVE'
                elif position != 1:
                    blocked = 'NOT_FIRST_IN_QUEUE'
                elif not client.eligible:
                    blocked = 'CLIENT_INELIGIBLE'
                elif available == 0:
                    blocked = 'NO_FREE_COPY'
            result.append(StaffPurchaseReservation(
                id=reservation.id, client=client, book=self._book(book), status=reservation.status.value,
                queue_position=position, requested_at=reservation.requested_at, pickup_date=row['pickup_date'],
                notified_at=reservation.notified_at, expires_at=reservation.expires_at,
                expired=reservation.expires_at is not None and reservation.expires_at < now,
                allocated_copy_id=reservation.allocated_copy_id, allocated_copy_barcode=row['allocated_barcode'],
                free_commercial_copies=available, can_allocate=waiting and blocked is None,
                allocation_blocked_reason=blocked))
        return result
