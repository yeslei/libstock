from datetime import datetime
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.core.exceptions import ApplicationError, BookNotFoundError
from app.repositories.purchase_request_repository import PurchaseRequestRepository
from app.schemas.purchase_request_schema import PurchaseRequestCreate, PurchaseRequestResponse
from app.core.business_dates import BUSINESS_ZONE as ZONE, business_today
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
            self.repository.expire_due_reservations(data.book_id, datetime.now(ZONE))
            require_eligible_client(self.repository, client_id, business_today())
            if book is None or not book.is_active:
                raise BookNotFoundError()
            if self.repository.find_pending(client_id, data.book_id) is not None:
                raise ApplicationError('Você já possui uma solicitação de compra pendente para este livro.', 'purchase_request_duplicate', 409)
            if self.repository.has_waiting_queue(data.book_id):
                raise ApplicationError('A fila de compra precisa ser atendida antes de novas retiradas.', 'purchase_queue_pending', 409)
            copy = self.repository.lock_available_copy(data.book_id)
            if copy is None:
                raise ApplicationError('Não há exemplar comercial disponível para compra.', 'purchase_unavailable', 409)
            request = self.repository.create(client_id, data.book_id, data.pickup_date, copy.id)
            response = PurchaseRequestResponse.model_validate(request)
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
