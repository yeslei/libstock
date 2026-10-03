from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.authentication import require_roles
from app.models.user import User
from app.repositories.client_tracking_repository import ClientTrackingRepository
from app.services.client_tracking_service import ClientTrackingService
from app.schemas.client_tracking_schema import TrackingItem, ReservePurchaseCreate, ReservePurchaseResponse

router = APIRouter(prefix='/api/v1', tags=['Acompanhamento do cliente'])


def get_client_tracking_service(db: Session = Depends(get_db)):
    return ClientTrackingService(db, ClientTrackingRepository(db))


@router.get('/loans/me', response_model=list[TrackingItem])
def my_loans(user: User = Depends(require_roles('USER')), service=Depends(get_client_tracking_service)):
    return service.loans(user.id)


@router.get('/purchase-reservations/me', response_model=list[TrackingItem])
def my_reservations(user: User = Depends(require_roles('USER')), service=Depends(get_client_tracking_service)):
    return service.reservations(user.id)


@router.post('/purchase-reservations', response_model=ReservePurchaseResponse, status_code=status.HTTP_201_CREATED)
def reserve_purchase(data: ReservePurchaseCreate, user: User = Depends(require_roles('USER')), service=Depends(get_client_tracking_service)):
    return service.reserve_purchase(user.id, data.book_id)


