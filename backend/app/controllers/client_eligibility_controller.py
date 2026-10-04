from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.authentication import require_roles
from app.models.user import User
from app.repositories.client_request_repository import ClientRequestRepository
from app.schemas.client_eligibility_schema import EligibilityResponse
from app.services.client_eligibility import ClientEligibilityService

router = APIRouter(prefix="/api/v1", tags=["Elegibilidade do cliente"])


def get_client_eligibility_service(db: Session = Depends(get_db)) -> ClientEligibilityService:
    return ClientEligibilityService(ClientRequestRepository(db))


@router.get("/me/eligibility", response_model=EligibilityResponse)
def my_eligibility(
    user: User = Depends(require_roles("USER")),
    service: ClientEligibilityService = Depends(get_client_eligibility_service),
) -> EligibilityResponse:
    return service.check(user.id)
