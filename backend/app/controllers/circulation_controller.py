from typing import Annotated
from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.authentication import require_roles
from app.models.user import User
from app.repositories.circulation_repository import CirculationRepository
from app.schemas.client_tracking_schema import CancelReservationRequest, CirculationResponse, ExpireReservationsResponse, PickupConfirmation
from app.services.circulation_service import CirculationService

ResourceId = Annotated[int, Path(gt=0, le=2**63 - 1)]
router = APIRouter(prefix='/api/v1/staff', tags=['Circulação pelo funcionário'])


def get_circulation_service(db: Session = Depends(get_db)):
    return CirculationService(db, CirculationRepository(db))


@router.post('/loan-requests/{request_id}/confirm-pickup', response_model=CirculationResponse)
def confirm_pickup(request_id: ResourceId, data: PickupConfirmation, user: User = Depends(require_roles('SELLER','ADMINISTRATOR')), service=Depends(get_circulation_service)):
    return service.confirm_pickup(request_id, data.copy_id, user.id)


@router.post('/loans/{loan_id}/confirm-return', response_model=CirculationResponse)
def confirm_return(loan_id: ResourceId, user: User = Depends(require_roles('SELLER','ADMINISTRATOR')), service=Depends(get_circulation_service)):
    return service.confirm_return(loan_id, user.id)


@router.post('/books/{book_id}/allocate-purchase', response_model=CirculationResponse)
def allocate_purchase(book_id: ResourceId, user: User = Depends(require_roles('SELLER','ADMINISTRATOR')), service=Depends(get_circulation_service)):
    return service.allocate_purchase(book_id, user.id)


@router.post('/purchase-reservations/{reservation_id}/confirm-sale', response_model=CirculationResponse)
def confirm_sale(reservation_id: ResourceId, user: User = Depends(require_roles('SELLER','ADMINISTRATOR')), service=Depends(get_circulation_service)):
    return service.confirm_sale(reservation_id, user.id)


@router.post('/purchase-reservations/expire', response_model=ExpireReservationsResponse)
def expire_purchase_reservations(user: User = Depends(require_roles('SELLER','ADMINISTRATOR')), service=Depends(get_circulation_service)):
    return service.expire_due_reservations(user.id)


@router.post('/purchase-reservations/{reservation_id}/cancel', response_model=CirculationResponse)
def cancel_purchase_reservation(reservation_id: ResourceId, data: CancelReservationRequest | None = None, user: User = Depends(require_roles('SELLER','ADMINISTRATOR')), service=Depends(get_circulation_service)):
    return service.cancel_reservation_by_staff(reservation_id, user.id, data.reason if data else None)
