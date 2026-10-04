from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.authentication import require_roles
from app.models.user import User
from app.repositories.purchase_request_repository import PurchaseRequestRepository
from app.schemas.purchase_request_schema import PurchaseRequestCreate, PurchaseRequestResponse
from app.services.purchase_request_service import PurchaseRequestService

router = APIRouter(prefix='/api/v1/purchase-requests', tags=['Solicitações de compra'])


def get_purchase_request_service(db: Session = Depends(get_db)):
    return PurchaseRequestService(db, PurchaseRequestRepository(db))


@router.post('', response_model=PurchaseRequestResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_request(data: PurchaseRequestCreate,
                            user: User = Depends(require_roles('USER')),
                            service: PurchaseRequestService = Depends(get_purchase_request_service)):
    return service.create(data, client_id=user.id)
