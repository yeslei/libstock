from fastapi import APIRouter, Depends, status

from app.core.database import get_db
from app.dependencies.authentication import require_roles
from app.models.user import User
from app.repositories.loan_request_repository import LoanRequestRepository
from app.schemas.loan_request_schema import LoanRequestCreate, LoanRequestResponse
from app.services.loan_request_service import LoanRequestService
from sqlalchemy.orm import Session


router = APIRouter(prefix="/api/v1/loan-requests", tags=["Solicitações de empréstimo"])


def get_loan_request_service(db: Session = Depends(get_db)):
    return LoanRequestService(db, LoanRequestRepository(db))


@router.post("", response_model=LoanRequestResponse, status_code=status.HTTP_201_CREATED)
def create_loan_request(data: LoanRequestCreate,
                        user: User = Depends(require_roles("USER")),
                        service: LoanRequestService = Depends(get_loan_request_service)):
    return service.create(data, client_id=user.id)
