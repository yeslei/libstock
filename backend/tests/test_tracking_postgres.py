from datetime import datetime, timedelta, timezone
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.models.domain import Copy, DestinationType, Employee, Loan, LoanStatus, PurchaseReservation, ReservationStatus
from app.schemas.loan_request_schema import LoanRequestCreate
from app.services.loan_request_service import LoanRequestService, business_today
from app.repositories.loan_request_repository import LoanRequestRepository
from app.services.client_tracking_service import ClientTrackingService
from app.repositories.client_tracking_repository import ClientTrackingRepository
from app.services.circulation_service import CirculationService
from app.repositories.circulation_repository import CirculationRepository
from test_client_requests_postgres import records


def test_loan_pending_active_overdue_returned(records, monkeypatch):
    engine, book_id, client_id = records
    with Session(engine) as db:
        staff = db.scalar(select(Employee.id).order_by(Employee.id))
        copy_id = db.scalar(select(Copy.id).where(Copy.book_id==book_id,Copy.destination==DestinationType.DIDACTIC))
        request = LoanRequestService(db,LoanRequestRepository(db)).create(LoanRequestCreate(book_id=book_id,pickup_date=business_today()), client_id=client_id)
        tracking = ClientTrackingService(db,ClientTrackingRepository(db))
        circulation = CirculationService(db, CirculationRepository(db))
        assert tracking.loans(client_id)[0].status == 'AWAITING_PICKUP'
        loan_id = circulation.confirm_pickup(request.id,copy_id,staff)['id']
        assert [item.status for item in tracking.loans(client_id)] == ['ACTIVE']
        loan = db.get(Loan,loan_id)
        monkeypatch.setattr('app.services.client_tracking_service.business_today', lambda: loan.due_date.date()+timedelta(days=10))
        assert tracking.loans(client_id)[0].status == 'OVERDUE'
        circulation.confirm_return(loan_id,staff)
        assert tracking.loans(client_id) == []


def test_purchase_waiting_allocated_sold(records):
    engine,book_id,client_id = records
    with Session(engine) as db:
        staff = db.scalar(select(Employee.id).order_by(Employee.id))
        copy = db.scalar(select(Copy).where(Copy.book_id==book_id,Copy.destination==DestinationType.COMMERCIAL))
        # Existing domain supports commercial copies in legacy loans.
        now=datetime.now(timezone.utc)
        loan=Loan(client_id=client_id,copy_id=copy.id,employee_id=staff,loan_date=now,due_date=now+timedelta(days=30),status=LoanStatus.OPEN)
        db.add(loan); db.commit()
        tracking=ClientTrackingService(db,ClientTrackingRepository(db))
        circulation = CirculationService(db, CirculationRepository(db))
        reservation=tracking.reserve_purchase(client_id,book_id)
        item=tracking.reservations(client_id)[0]
        assert item.status=='WAITING' and item.queue_position==1
        circulation.confirm_return(loan.id,staff)
        circulation.allocate_purchase(book_id,staff)
        item=tracking.reservations(client_id)[0]
        assert item.status=='NOTIFIED' and item.copy_barcode==copy.barcode
        assert item.expires_at is None
        circulation.confirm_sale(reservation.id,staff)
        assert tracking.reservations(client_id)==[]
        db.expire_all()
        assert db.get(Copy,copy.id).status.value=='SOLD'


def test_tracking_queries_do_not_expose_other_client(records):
    engine,book_id,client_id=records
    with Session(engine) as db:
        repo=ClientTrackingRepository(db)
        LoanRequestService(db,LoanRequestRepository(db)).create(LoanRequestCreate(book_id=book_id,pickup_date=business_today()),client_id=client_id)
        assert len(repo.pending_loans(client_id))==1
        assert repo.pending_loans(client_id+100000)==[]
        assert repo.active_loans(client_id+100000)==[]
        assert repo.active_reservations(client_id+100000)==[]
