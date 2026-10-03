from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.core.business_dates import BUSINESS_ZONE as ZONE, business_today
from app.core.exceptions import ApplicationError, BookNotFoundError
from app.models.domain import ReservationStatus
from app.repositories.client_tracking_repository import ClientTrackingRepository
from app.schemas.client_tracking_schema import TrackingItem, ReservePurchaseResponse
from app.services.client_eligibility import require_eligible_client


class ClientTrackingService:
    def __init__(self, db, repository: ClientTrackingRepository):
        self.db = db
        self.repository = repository

    def require_client(self, client_id):
        if not self.repository.client_exists(client_id):
            raise ApplicationError('É necessário um cadastro de cliente.', 'client_required', 403)

    def loans(self, client_id):
        self.require_client(client_id)
        items = []
        for request, book in self.repository.pending_loans(client_id):
            items.append(TrackingItem(id=request.id, book_id=book.id, title=book.title, author=book.author,
                cover_url=book.cover_url, status='AWAITING_PICKUP', pickup_date=request.pickup_date))
        for loan, copy, book in self.repository.active_loans(client_id):
            due = loan.due_date.astimezone(ZONE).date()
            late = max(0, (business_today() - due).days)
            items.append(TrackingItem(id=loan.id, book_id=book.id, title=book.title, author=book.author,
                cover_url=book.cover_url, status='OVERDUE' if late else 'ACTIVE', copy_barcode=copy.barcode,
                pickup_date=loan.loan_date.astimezone(ZONE).date(), due_date=due, days_late=late))
        return items

    def reservations(self, client_id):
        self.require_client(client_id)
        return [TrackingItem(id=reservation.id, book_id=book.id, title=book.title, author=book.author,
            cover_url=book.cover_url, status=reservation.status.value,
            copy_barcode=copy.barcode if copy else None,
            queue_position=self.repository.waiting_position(reservation) if reservation.status == ReservationStatus.WAITING else None,
            available_since=reservation.notified_at, expires_at=reservation.expires_at)
            for reservation, book, copy in self.repository.active_reservations(client_id)]

    def validate_client(self, client_id):
        require_eligible_client(self.repository, client_id, business_today())

    def reserve_purchase(self, client_id, book_id):
        try:
            book = self.repository.lock_book(book_id)
            self.validate_client(client_id)
            if book is None or not book.is_active:
                raise BookNotFoundError()
            if self.repository.existing_reservation(client_id, book_id):
                raise ApplicationError('Você já possui uma reserva de compra em andamento.', 'reservation_duplicate', 409)
            if not self.repository.has_reservable_commercial_copy(book_id):
                raise ApplicationError('Não há exemplar comercial para reserva de compra.', 'reservation_unavailable', 409)
            free = self.repository.has_free_commercial_copy(book_id)
            if free:
                raise ApplicationError('Há exemplar disponível. Solicite a compra com data de retirada.', 'purchase_available', 409)
            reservation = self.repository.create_reservation(client_id, book_id)
            response = ReservePurchaseResponse.model_validate(reservation).model_copy(
                update={'queue_position': self.repository.waiting_position(reservation)},
            )
            self.db.commit()
            return response
        except ApplicationError:
            self.db.rollback()
            raise
        except IntegrityError as exc:
            self.db.rollback()
            name = getattr(getattr(exc.orig, 'diag', None), 'constraint_name', '')
            if name == 'uq_active_reservation_client_book':
                raise ApplicationError('Você já possui uma reserva de compra em andamento.', 'reservation_duplicate', 409) from exc
            raise ApplicationError('Não foi possível salvar a reserva.', 'reservation_persistence_error', 500) from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ApplicationError('Não foi possível salvar a reserva.', 'reservation_persistence_error', 500) from exc
