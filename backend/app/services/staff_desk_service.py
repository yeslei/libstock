from datetime import datetime, time, timedelta
from sqlalchemy.exc import SQLAlchemyError
from app.core.business_dates import BUSINESS_ZONE as ZONE, business_today, overdue_cutoff
from app.core.exceptions import ApplicationError
from app.models.domain import DestinationType, ReservationStatus
from app.repositories.staff_desk_repository import StaffDeskRepository
from app.schemas.staff_desk_schema import (
    EligibleCopy, StaffBook, StaffCatalogBook, StaffCatalogBookDetail, StaffCatalogCopy, StaffClient,
    StaffClientPendencies, StaffCopyBook, StaffCopyLookup, StaffDashboard, StaffLoan, StaffLoanRequest,
    StaffPurchaseReservation,
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
        return today, overdue_cutoff(today)

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

    def dashboard(self, actor_id):
        """Indicadores somente leitura do painel do balcão."""
        today, cutoff = self._guard(actor_id)
        next_cutoff = datetime.combine(today + timedelta(days=1), time.min, ZONE)
        return StaffDashboard(**self._read(lambda: self.repository.dashboard_counts(cutoff, next_cutoff)))

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
        return self._loans(today, cutoff, term, client_id, limit)

    def client_pendencies(self, actor_id, client_id):
        """Somente leitura: não sincroniza penalidade; atraso pela regra V2 (calendário de São Paulo)."""
        today, cutoff = self._guard(actor_id)
        row = self._read(lambda: self.repository.client_summary(client_id, cutoff))
        if row is None:
            raise ApplicationError('Cliente não encontrado.', 'client_not_found', 404)
        overdue = [loan for loan in self._loans(today, cutoff, None, client_id, 100) if loan.status == 'OVERDUE']
        return StaffClientPendencies(client=self._client(row), overdue_loans=overdue)

    def _loans(self, today, cutoff, term, client_id, limit):
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
        book_ids = sorted({row['Book'].id for row in rows})
        # Reservas destinadas vencidas ainda não gravadas liberam o exemplar na próxima escrita da obra (a consulta não grava).
        releasable = self._read(lambda: self.repository.expired_notified_counts(book_ids, now))
        # Primeira reserva ELEGÍVEL da fila completa de cada obra (inelegíveis mantêm a posição, mas são puladas).
        first_eligible = {}
        for queued in self._read(lambda: self.repository.waiting_queues(book_ids, cutoff)):
            if queued['book_id'] not in first_eligible and self._client(queued).eligible:
                first_eligible[queued['book_id']] = queued['reservation_id']
        result = []
        for row in rows:
            reservation, book, client = row['PurchaseReservation'], row['Book'], self._client(row)
            waiting = reservation.status == ReservationStatus.WAITING
            position = row['waiting_position'] if waiting else None
            available = free.get(book.id, 0) + releasable.get(book.id, 0)
            blocked = None
            if waiting:
                if not book.is_active:
                    blocked = 'BOOK_INACTIVE'
                elif not client.eligible:
                    blocked = 'CLIENT_INELIGIBLE'
                elif first_eligible.get(book.id) != reservation.id:
                    blocked = 'NOT_FIRST_ELIGIBLE'
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

    @staticmethod
    def _catalog_book(row):
        book = row['Book']
        return dict(id=book.id, title=book.title, author=book.author, isbn=book.isbn, genre=book.genre,
                    is_active=book.is_active, total_copies=row['total_copies'],
                    didactic_copies=row['didactic_copies'], commercial_copies=row['commercial_copies'])

    def catalog_books(self, actor_id, term, limit):
        """Acervo somente leitura para o balcão (obras e contagem de exemplares)."""
        self._guard(actor_id)
        rows = self._read(lambda: self.repository.catalog_books(self._term(term), limit))
        return [StaffCatalogBook(**self._catalog_book(row)) for row in rows]

    def catalog_book(self, actor_id, book_id):
        self._guard(actor_id)
        row = self._read(lambda: self.repository.catalog_book(book_id))
        if row is None:
            raise ApplicationError('Obra não encontrada.', 'book_not_found', 404)
        copies = self._read(lambda: self.repository.book_copies(book_id))
        return StaffCatalogBookDetail(**self._catalog_book(row), copies=[
            StaffCatalogCopy(id=item['Copy'].id, barcode=item['Copy'].barcode, destination=item['Copy'].destination,
                             status=item['Copy'].status, condition=item['Copy'].condition,
                             sale_price=item['Copy'].sale_price, is_active=item['Copy'].is_active,
                             free=bool(item['free']), allocated_for_purchase=bool(item['allocated_for_purchase']))
            for item in copies])

    def copy_lookup(self, actor_id, term, limit):
        """Exemplares por código, ISBN, título ou autor. A venda só é possível para comercial livre."""
        term = self._term(term)
        if term is None:
            raise ApplicationError('Informe o código do exemplar, o ISBN ou o título.', 'search_term_required', 422)
        self._guard(actor_id)
        rows = self._read(lambda: self.repository.copy_lookup(term, limit))
        book_ids = sorted({row['Book'].id for row in rows})
        free_counts = self._read(lambda: self.repository.free_commercial_counts(book_ids))
        result = []
        for row in rows:
            copy, book, free = row['Copy'], row['Book'], bool(row['free'])
            if copy.destination == DestinationType.DIDACTIC:
                block = 'DIDACTIC'
            elif not free:
                block = 'NOT_AVAILABLE'
            else:
                block = None
            result.append(StaffCopyLookup(
                id=copy.id, barcode=copy.barcode, destination=copy.destination, status=copy.status,
                condition=copy.condition, sale_price=copy.sale_price,
                book=StaffCopyBook(id=book.id, title=book.title, author=book.author, isbn=book.isbn,
                                   is_active=book.is_active),
                free=free, free_commercial_copies=free_counts.get(book.id, 0), sellable=block is None,
                sale_block_reason=block))
        return result
