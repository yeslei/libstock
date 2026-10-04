from datetime import datetime
from functools import wraps
from sqlalchemy.exc import SQLAlchemyError
from app.core.business_dates import BUSINESS_ZONE as ZONE, business_today, loan_due_at, reservation_pickup_deadline
from app.core.exceptions import ApplicationError, BookNotFoundError
from app.models.domain import CopyStatus, DestinationType, LoanStatus, ReservationStatus, SaleStatus
from app.repositories.circulation_repository import CirculationRepository
from app.services.client_eligibility import is_client_locked_eligible, require_eligible_client


def transactional(operation):
    @wraps(operation)
    def wrapped(self, *args, **kwargs):
        try:
            result = operation(self, *args, **kwargs)
            self.db.commit()
            return result
        except ApplicationError:
            self.db.rollback()
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ApplicationError('Não foi possível concluir a operação.', 'circulation_persistence_error', 500) from exc
    return wrapped


class CirculationService:
    def __init__(self, db, repository: CirculationRepository):
        self.db = db
        self.repository = repository

    def validate_client(self, client_id):
        require_eligible_client(self.repository, client_id, business_today())

    def require_employee(self, actor_id):
        if not self.repository.is_active_employee(actor_id):
            raise ApplicationError('Cadastro de funcionário ativo necessário.', 'employee_record_required', 403)
        self.repository.set_audit_actor(actor_id)

    @transactional
    def confirm_pickup(self, request_id, copy_id, actor_id):
        self.require_employee(actor_id)
        request = self.repository.find_request(request_id)
        if request is None:
            raise ApplicationError('Solicitação não encontrada.', 'loan_request_not_found', 404)
        book = self.repository.lock_book(request.book_id)
        request = self.repository.find_request(request_id, lock=True)
        if request.loan_id is not None:
            raise ApplicationError('Retirada já confirmada.', 'pickup_already_confirmed', 409)
        self.validate_client(request.client_id)
        copy = self.repository.lock_free_copy(request.book_id, DestinationType.DIDACTIC, copy_id)
        if not book or not book.is_active or copy is None:
            raise ApplicationError('Exemplar didático indisponível para retirada.', 'loan_unavailable', 409)
        now = datetime.now(ZONE)
        due = loan_due_at(now)
        loan = self.repository.create_loan(client_id=request.client_id, copy_id=copy.id, employee_id=actor_id,
                    loan_date=now, due_date=due, status=LoanStatus.OPEN)
        return {'id': loan.id}

    @transactional
    def confirm_return(self, loan_id, actor_id):
        self.require_employee(actor_id)
        loan = self.repository.find_loan(loan_id)
        if loan is None:
            raise ApplicationError('Empréstimo não encontrado.', 'loan_not_found', 404)
        if loan.status != LoanStatus.OPEN:
            raise ApplicationError('Empréstimo já encerrado.', 'loan_already_closed', 409)
        loan.returned_at = datetime.now(ZONE)
        loan.status = LoanStatus.RETURNED
        self.repository.flush()
        return {'id': loan.id}

    @transactional
    def allocate_purchase(self, book_id, actor_id):
        self.require_employee(actor_id)
        book = self.repository.lock_book(book_id)
        if book is None or not book.is_active:
            raise BookNotFoundError()
        now = datetime.now(ZONE)
        self.repository.expire_due_reservations(book_id, now)
        waiting = self.repository.waiting_queue(book_id)
        if not waiting:
            raise ApplicationError('Não há reserva aguardando disponibilidade.', 'reservation_not_found', 404)
        today = business_today()
        reservation = next((item for item in waiting
                            if is_client_locked_eligible(self.repository, item.client_id, today)), None)
        if reservation is None:
            raise ApplicationError('Nenhuma reserva da fila possui cliente elegível.', 'no_eligible_reservation', 409)
        copy = self.repository.lock_free_copy(book_id, DestinationType.COMMERCIAL)
        if copy is None:
            raise ApplicationError('Não há exemplar comercial disponível.', 'purchase_unavailable', 409)
        reservation.allocated_copy_id = copy.id
        reservation.status = ReservationStatus.NOTIFIED
        reservation.notified_at = now
        reservation.expires_at = reservation_pickup_deadline(now)
        self.repository.flush()
        return {'id': reservation.id}

    @transactional
    def confirm_sale(self, reservation_id, actor_id):
        self.require_employee(actor_id)
        reservation = self.repository.find_reservation(reservation_id)
        if reservation is None:
            raise ApplicationError('Reserva não encontrada.', 'reservation_not_found', 404)
        book = self.repository.lock_book(reservation.book_id)
        if book is None or not book.is_active:
            raise BookNotFoundError()
        reservation = self.repository.find_reservation(reservation_id, lock=True)
        if reservation.status != ReservationStatus.NOTIFIED or reservation.allocated_copy_id is None:
            raise ApplicationError('Reserva ainda não está disponível para retirada.', 'reservation_not_ready', 409)
        if reservation.expires_at is not None and reservation.expires_at < datetime.now(ZONE):
            # A expiração precisa ser efetivada mesmo com a venda recusada: confirma antes de responder o erro.
            reservation.status = ReservationStatus.EXPIRED
            self.repository.flush()
            self.db.commit()
            raise ApplicationError('O prazo de retirada expirou.', 'reservation_expired', 409)
        self.validate_client(reservation.client_id)
        copy = self.repository.lock_allocated_copy(reservation.allocated_copy_id)
        if copy is None or copy.destination != DestinationType.COMMERCIAL or not copy.is_active or copy.status != CopyStatus.AVAILABLE:
            raise ApplicationError('Exemplar comercial indisponível.', 'purchase_unavailable', 409)
        sale = self.repository.create_sale(reservation.client_id, actor_id, copy)
        sale.status = SaleStatus.CONFIRMED
        self.repository.flush()
        return {'id': sale.id}

    def _cancel(self, reservation_id, actor_id, *, client_scope, reason=None):
        reservation = self.repository.find_reservation(reservation_id)
        if reservation is None or (client_scope and reservation.client_id != actor_id):
            raise ApplicationError('Reserva não encontrada.', 'reservation_not_found', 404)
        self.repository.lock_book(reservation.book_id)
        reservation = self.repository.find_reservation(reservation_id, lock=True)
        if (reservation.status == ReservationStatus.NOTIFIED and reservation.expires_at is not None
                and reservation.expires_at < datetime.now(ZONE)):
            reservation.status = ReservationStatus.EXPIRED
            self.repository.flush()
            self.db.commit()
        if reservation.status not in (ReservationStatus.WAITING, ReservationStatus.NOTIFIED):
            raise ApplicationError('A reserva já foi encerrada e não pode ser cancelada.', 'reservation_not_cancellable',
                                   409, {'status': reservation.status.value})
        reservation.status = ReservationStatus.CANCELLED
        self.repository.flush()
        self.repository.record_cancellation(reservation.id, actor_id, 'USER' if client_scope else 'STAFF', reason)
        return {'id': reservation.id}

    @transactional
    def cancel_reservation_by_staff(self, reservation_id, actor_id, reason=None):
        self.require_employee(actor_id)
        return self._cancel(reservation_id, actor_id, client_scope=False, reason=reason)

    @transactional
    def cancel_own_reservation(self, reservation_id, client_id):
        if not self.repository.client_exists(client_id):
            raise ApplicationError('É necessário um cadastro de cliente.', 'client_required', 403)
        return self._cancel(reservation_id, client_id, client_scope=True)

    @transactional
    def expire_due_reservations(self, actor_id):
        self.require_employee(actor_id)
        now = datetime.now(ZONE)
        expired = 0
        for book_id in self.repository.books_with_due_reservations(now):
            self.repository.lock_book(book_id)
            expired += self.repository.expire_due_reservations(book_id, now)
        return {'expired': expired}
