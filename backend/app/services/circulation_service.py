from datetime import datetime
from functools import wraps
from sqlalchemy.exc import SQLAlchemyError
from app.core.business_dates import BUSINESS_ZONE as ZONE, business_today, loan_due_at
from app.core.exceptions import ApplicationError, BookNotFoundError
from app.models.domain import CopyStatus, DestinationType, LoanStatus, ReservationStatus, SaleStatus
from app.repositories.circulation_repository import CirculationRepository
from app.services.client_eligibility import require_eligible_client


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
        reservation = self.repository.first_waiting(book_id)
        if reservation is None:
            raise ApplicationError('Não há reserva aguardando disponibilidade.', 'reservation_not_found', 404)
        self.validate_client(reservation.client_id)
        copy = self.repository.lock_free_copy(book_id, DestinationType.COMMERCIAL)
        if copy is None:
            raise ApplicationError('Não há exemplar comercial disponível.', 'purchase_unavailable', 409)
        reservation.allocated_copy_id = copy.id
        reservation.status = ReservationStatus.NOTIFIED
        reservation.notified_at = datetime.now(ZONE)
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
        self.validate_client(reservation.client_id)
        if reservation.expires_at is not None and reservation.expires_at < datetime.now(ZONE):
            raise ApplicationError('O prazo de retirada expirou.', 'reservation_expired', 409)
        copy = self.repository.lock_allocated_copy(reservation.allocated_copy_id)
        if copy is None or copy.destination != DestinationType.COMMERCIAL or not copy.is_active or copy.status != CopyStatus.AVAILABLE:
            raise ApplicationError('Exemplar comercial indisponível.', 'purchase_unavailable', 409)
        sale = self.repository.create_sale(reservation.client_id, actor_id, copy)
        sale.status = SaleStatus.CONFIRMED
        self.repository.flush()
        return {'id': sale.id}
