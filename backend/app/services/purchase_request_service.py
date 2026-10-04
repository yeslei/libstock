from datetime import datetime
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.core.exceptions import ApplicationError, BookNotFoundError
from app.repositories.purchase_request_repository import PurchaseRequestRepository
from app.schemas.purchase_request_schema import PurchaseRequestCreate, PurchaseRequestResponse
from app.core.business_dates import BUSINESS_ZONE as ZONE, business_today, reservation_pickup_deadline
from app.services.client_eligibility import require_eligible_client


class PurchaseRequestService:
    def __init__(self, db, repository: PurchaseRequestRepository):
        self.db = db
        self.repository = repository

    def create(self, data: PurchaseRequestCreate, *, client_id: int) -> PurchaseRequestResponse:
        if data.pickup_date < business_today():
            raise ApplicationError('Informe uma data de retirada válida, a partir de hoje.', 'invalid_pickup_date', 422)
        try:
            book = self.repository.lock_book(data.book_id)
            now = datetime.now(ZONE)
            self.repository.expire_due_reservations(data.book_id, now)
            require_eligible_client(self.repository, client_id, business_today())
            if book is None or not book.is_active:
                raise BookNotFoundError()
            if self.repository.find_pending(client_id, data.book_id) is not None:
                raise ApplicationError('Você já possui uma solicitação de compra pendente para este livro.', 'purchase_request_duplicate', 409)
            copy = None
            if self.repository.has_waiting_queue(data.book_id):
                # Havendo fila WAITING a precedência é preservada: entra no fim da fila, mesmo com exemplar livre.
                if not self.repository.has_queueable_commercial_copy(data.book_id):
                    raise ApplicationError('Não há exemplar comercial disponível para compra.', 'purchase_unavailable', 409)
            else:
                copy = self.repository.lock_available_copy(data.book_id)
                if copy is None:
                    raise ApplicationError('Não há exemplar comercial disponível para compra.', 'purchase_unavailable', 409)
                if data.pickup_date > reservation_pickup_deadline(now).astimezone(ZONE).date():
                    raise ApplicationError('A data de retirada não pode ultrapassar o prazo de retirada da reserva.',
                                           'pickup_date_after_deadline', 422)
            request = self.repository.create(client_id, data.book_id, data.pickup_date, copy.id if copy else None,
                                             notified_at=now)
            response = PurchaseRequestResponse.model_validate(request).model_copy(
                update={'reservation_status': 'NOTIFIED' if copy else 'WAITING'})
            self.db.commit()
            return response
        except IntegrityError as exc:
            self.db.rollback()
            constraint = getattr(getattr(exc.orig, 'diag', None), 'constraint_name', None)
            if constraint in ('uq_pending_purchase_request_client_book', 'uq_active_reservation_client_book'):
                raise ApplicationError('Você já possui uma solicitação de compra pendente para este livro.', 'purchase_request_duplicate', 409) from exc
            raise ApplicationError('Não foi possível salvar a solicitação de compra.', 'purchase_request_persistence_error', 500) from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ApplicationError('Não foi possível salvar a solicitação de compra.', 'purchase_request_persistence_error', 500) from exc
        except ApplicationError:
            self.db.rollback()
            raise
