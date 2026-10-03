
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.exceptions import ApplicationError, BookNotFoundError
from app.repositories.loan_request_repository import LoanRequestRepository
from app.schemas.loan_request_schema import LoanRequestCreate, LoanRequestResponse


from app.core.business_dates import business_today, next_month
from app.services.client_eligibility import require_eligible_client


class LoanRequestService:
    def __init__(self, db, repository: LoanRequestRepository):
        self.db = db
        self.repository = repository

    def create(self, data: LoanRequestCreate, *, client_id: int) -> LoanRequestResponse:
        if data.pickup_date < business_today():
            raise ApplicationError("Informe uma data de retirada válida, a partir de hoje.", "invalid_pickup_date", 422)
        try:
            book = self.repository.lock_book(data.book_id)
            require_eligible_client(self.repository, client_id, business_today())
            if book is None or not book.is_active:
                raise BookNotFoundError()
            if self.repository.find_pending(client_id, data.book_id) is not None:
                raise ApplicationError("Você já possui uma solicitação pendente para este livro.", "loan_request_duplicate", 409)
            if self.repository.lock_available_copy(data.book_id) is None:
                raise ApplicationError("Não há exemplar disponível para empréstimo.", "loan_unavailable", 409)
            request = self.repository.create(client_id, data.book_id, data.pickup_date, next_month(data.pickup_date))
            response = LoanRequestResponse.model_validate(request)
            self.db.commit()
            return response
        except IntegrityError as exc:
            self.db.rollback()
            constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            if constraint == "uq_pending_loan_request_client_book":
                raise ApplicationError("Você já possui uma solicitação pendente para este livro.", "loan_request_duplicate", 409) from exc
            raise ApplicationError("Não foi possível salvar a solicitação.", "loan_request_persistence_error", 500) from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ApplicationError("Não foi possível salvar a solicitação.", "loan_request_persistence_error", 500) from exc
        except ApplicationError:
            self.db.rollback()
            raise
