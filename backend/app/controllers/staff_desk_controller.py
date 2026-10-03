from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.authentication import require_roles
from app.models.user import User
from app.repositories.staff_desk_repository import StaffDeskRepository
from app.schemas.staff_desk_schema import StaffClient, StaffClientPendencies, StaffLoan, StaffLoanRequest, StaffPurchaseReservation
from app.services.staff_desk_service import StaffDeskService

router = APIRouter(prefix='/api/v1/staff', tags=['Balcão do funcionário'])
Term = Annotated[str | None, Query(max_length=100)]
ClientFilter = Annotated[int | None, Query(gt=0, le=2**31 - 1)]
Limit = Annotated[int, Query(ge=1, le=100)]
staff_only = require_roles('SELLER', 'ADMINISTRATOR')


def get_staff_desk_service(db: Session = Depends(get_db)):
    return StaffDeskService(db, StaffDeskRepository(db))


@router.get('/clients', response_model=list[StaffClient])
def search_clients(q: Annotated[str, Query(min_length=2, max_length=100)], limit: Limit = 20,
                   user: User = Depends(staff_only), service=Depends(get_staff_desk_service)):
    return service.search_clients(q, user.id, limit)


@router.get('/clients/{client_id}/pendencies', response_model=StaffClientPendencies)
def client_pendencies(client_id: Annotated[int, Path(gt=0, le=2**31 - 1)],
                      user: User = Depends(staff_only), service=Depends(get_staff_desk_service)):
    return service.client_pendencies(user.id, client_id)


@router.get('/loan-requests', response_model=list[StaffLoanRequest])
def list_loan_requests(q: Term = None, client_id: ClientFilter = None, limit: Limit = 50,
                       user: User = Depends(staff_only), service=Depends(get_staff_desk_service)):
    return service.loan_requests(user.id, q, client_id, limit)


@router.get('/loans', response_model=list[StaffLoan])
def list_open_loans(q: Term = None, client_id: ClientFilter = None, limit: Limit = 50,
                    user: User = Depends(staff_only), service=Depends(get_staff_desk_service)):
    return service.loans(user.id, q, client_id, limit)


@router.get('/purchase-reservations', response_model=list[StaffPurchaseReservation])
def list_purchase_reservations(q: Term = None, client_id: ClientFilter = None,
                               status: Literal['WAITING', 'NOTIFIED'] | None = None, limit: Limit = 50,
                               user: User = Depends(staff_only), service=Depends(get_staff_desk_service)):
    return service.purchase_reservations(user.id, q, client_id, status, limit)
