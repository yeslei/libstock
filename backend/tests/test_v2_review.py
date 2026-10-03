"""Regressions found in the V2 review; PostgreSQL cases use a disposable DB."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.models.domain import Client, Copy, DestinationType, Employee, Loan, LoanStatus, Profile, PurchaseReservation, ReservationStatus, Role, Sale, SaleItem, SaleStatus, UserRole
from app.models.user import User
from app.repositories.catalog_repository import CatalogRepository, GenreRepository
from app.repositories.circulation_repository import CirculationRepository
from app.repositories.client_tracking_repository import ClientTrackingRepository
from app.repositories.loan_request_repository import LoanRequestRepository
from app.repositories.purchase_request_repository import PurchaseRequestRepository
from app.schemas.loan_request_schema import LoanRequestCreate
from app.schemas.purchase_request_schema import PurchaseRequestCreate
from app.services.catalog_service import CatalogService
from app.services.circulation_service import CirculationService
from app.services.client_tracking_service import ClientTrackingService
from app.services.loan_request_service import LoanRequestService, business_today
from app.services.purchase_request_service import PurchaseRequestService
from test_client_requests_postgres import records
from test_loan_requests import setup_service
from test_purchase_requests import purchase


@pytest.mark.parametrize('kind', ['loan', 'purchase'])
def test_overdue_client_cannot_bypass_validation(setup_service, purchase, kind):
    service, db, repo = setup_service if kind == 'loan' else purchase
    repo.has_overdue_loan.return_value = True
    payload = (LoanRequestCreate if kind == 'loan' else PurchaseRequestCreate)(
        book_id=10, pickup_date=date(2026, 10, 31),
    )
    with pytest.raises(ApplicationError) as error:
        service.create(payload, client_id=7)
    assert error.value.code == 'client_ineligible'
    repo.create.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def second_client(db):
    role = db.scalar(select(Role.id).where(Role.code == 'USER'))
    user = User(name='Outro cliente teste', email=f'{uuid4().hex}@test.invalid', password_hash='test')
    db.add(user); db.flush()
    db.add(Profile(id=user.id)); db.flush()
    db.add_all([Client(id=user.id), UserRole(user_id=user.id, role_id=role)])
    db.commit()
    return user.id


def ready_purchase(db, book_id, client_id):
    return PurchaseRequestService(db, PurchaseRequestRepository(db)).create(
        PurchaseRequestCreate(book_id=book_id, pickup_date=business_today()), client_id=client_id,
    )


def staff_for(db, client_id):
    return db.scalar(select(Employee.id).where(Employee.id != client_id).order_by(Employee.id.desc()))


def test_catalog_and_details_agree_about_allocated_stock(records):
    engine, book_id, client_id = records
    with Session(engine) as db:
        ready_purchase(db, book_id, client_id)
        service = CatalogService(db=db, catalog_repository=CatalogRepository(db), genre_repository=GenreRepository(db))
        detail = service.get_public_book(book_id)
        offer = next(offer for offer in detail.offers if offer.destination == DestinationType.COMMERCIAL)
        assert not offer.available
        assert not detail.availability.sale.available
        assert detail.availability.sale.available_count == 0
        assert detail.availability.sale.can_reserve
        assert not LoanRequestRepository(db).lock_available_copy(book_id).destination == DestinationType.COMMERCIAL


def test_new_reservation_returns_current_position_excluding_ready_clients(records):
    engine, book_id, client_id = records
    with Session(engine) as db:
        other = second_client(db)
        ready_purchase(db, book_id, client_id)
        tracking = ClientTrackingService(db, ClientTrackingRepository(db))
        reservation = tracking.reserve_purchase(other, book_id)
        assert db.get(PurchaseReservation, reservation.id).queue_position == 2
        assert reservation.queue_position == tracking.reservations(other)[0].queue_position == 1


@pytest.mark.parametrize('operation', ['sale_other_client', 'inactivate', 'convert', 'loan'])
def test_allocated_copy_is_protected_in_database(records, operation):
    engine, book_id, client_id = records
    with Session(engine) as db:
        other = second_client(db)
        ready_purchase(db, book_id, client_id)
        reservation = db.scalar(select(PurchaseReservation).where(
            PurchaseReservation.client_id == client_id, PurchaseReservation.book_id == book_id))
        copy_id = reservation.allocated_copy_id
        actor = staff_for(db, client_id)
        db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(actor)})
        with pytest.raises(SQLAlchemyError):
            if operation == 'sale_other_client':
                sale = Sale(client_id=other, employee_id=actor, status=SaleStatus.PENDING)
                db.add(sale); db.flush()
                db.add(SaleItem(sale_id=sale.id, copy_id=copy_id, unit_price=25)); db.flush()
            elif operation == 'loan':
                now = datetime.now(timezone.utc)
                db.add(Loan(client_id=other, copy_id=copy_id, employee_id=actor,
                    loan_date=now, due_date=now+timedelta(days=30), status=LoanStatus.OPEN)); db.flush()
            elif operation == 'inactivate':
                db.execute(text('UPDATE copies SET is_active=false WHERE id=:id'), {'id': copy_id})
            else:
                db.execute(text("UPDATE copies SET destination='DIDACTIC', sale_price=NULL WHERE id=:id"), {'id': copy_id})
        db.rollback()
        assert db.get(Copy, copy_id).is_active
        assert db.get(Copy, copy_id).destination == DestinationType.COMMERCIAL
        assert db.get(PurchaseReservation, reservation.id).status == ReservationStatus.NOTIFIED


def test_two_clients_cannot_allocate_the_same_commercial_copy(records):
    engine, book_id, client_id = records
    with Session(engine) as db:
        other = second_client(db)
    barrier = Barrier(2)
    def submit(id):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:
                ready_purchase(db, book_id, id)
                return 201
            except ApplicationError as error:
                return error.status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, [client_id, other]))
    assert sorted(results) == [201, 409]
    with Session(engine) as db:
        assert len(list(db.scalars(select(PurchaseReservation).where(
            PurchaseReservation.book_id == book_id, PurchaseReservation.status == ReservationStatus.NOTIFIED)))) == 1


def test_fifo_position_advances_after_first_client_is_allocated(records):
    engine, book_id, client_id = records
    with Session(engine) as db:
        other = second_client(db)
        actor = staff_for(db, client_id)
        copy = db.scalar(select(Copy).where(Copy.book_id == book_id, Copy.destination == DestinationType.COMMERCIAL))
        now = datetime.now(timezone.utc)
        loan = Loan(client_id=client_id, copy_id=copy.id, employee_id=actor,
            loan_date=now, due_date=now+timedelta(days=30), status=LoanStatus.OPEN)
        db.add(loan); db.commit()
        tracking = ClientTrackingService(db, ClientTrackingRepository(db))
        first = tracking.reserve_purchase(client_id, book_id)
        tracking.reserve_purchase(other, book_id)
        assert tracking.reservations(other)[0].queue_position == 2
        circulation = CirculationService(db, CirculationRepository(db))
        circulation.confirm_return(loan.id, actor)
        circulation.allocate_purchase(book_id, actor)
        assert db.get(PurchaseReservation, first.id).status == ReservationStatus.NOTIFIED
        assert tracking.reservations(other)[0].queue_position == 1


def test_inactive_employee_cannot_confirm_pickup(records):
    engine, book_id, client_id = records
    with Session(engine) as db:
        actor = staff_for(db, client_id)
        request = LoanRequestService(db, LoanRequestRepository(db)).create(
            LoanRequestCreate(book_id=book_id, pickup_date=business_today()), client_id=client_id)
        copy_id = db.scalar(select(Copy.id).where(Copy.book_id == book_id, Copy.destination == DestinationType.DIDACTIC))
        db.get(Profile, actor).is_active = False; db.commit()
        with pytest.raises(ApplicationError) as error:
            CirculationService(db, CirculationRepository(db)).confirm_pickup(request.id, copy_id, actor)
        assert error.value.status_code == 403
        assert ClientTrackingService(db, ClientTrackingRepository(db)).loans(client_id)[0].status == 'AWAITING_PICKUP'


def test_sale_commit_failure_keeps_reservation_and_inventory(records):
    engine, book_id, client_id = records
    with Session(engine) as db:
        ready_purchase(db, book_id, client_id)
        actor = staff_for(db, client_id)
        reservation = db.scalar(select(PurchaseReservation).where(PurchaseReservation.book_id == book_id))
        reservation_id, copy_id = reservation.id, reservation.allocated_copy_id
    class FailedCommitSession(Session):
        def commit(self):
            raise SQLAlchemyError('forced commit failure')
    with FailedCommitSession(engine) as db:
        with pytest.raises(ApplicationError) as error:
            CirculationService(db, CirculationRepository(db)).confirm_sale(reservation_id, actor)
        assert error.value.code == 'circulation_persistence_error'
    with Session(engine) as db:
        assert db.get(PurchaseReservation, reservation_id).status == ReservationStatus.NOTIFIED
        assert db.get(Copy, copy_id).status.value == 'AVAILABLE'
        assert db.scalar(select(Sale.id).where(Sale.client_id == client_id)) is None


def test_didactic_only_book_cannot_enter_purchase_queue(records):
    engine, book_id, client_id = records
    with Session(engine) as db:
        actor = staff_for(db, client_id)
        db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(actor)})
        db.execute(text("UPDATE copies SET is_active=false WHERE book_id=:id AND destination='COMMERCIAL'"), {'id': book_id})
        db.commit()
        with pytest.raises(ApplicationError) as error:
            ClientTrackingService(db, ClientTrackingRepository(db)).reserve_purchase(client_id, book_id)
        assert error.value.code == 'reservation_unavailable'


def test_return_audit_identifies_actual_staff_member(records):
    engine, book_id, client_id = records
    with Session(engine) as db:
        original_actor = staff_for(db, client_id)
        different_actor = db.scalar(select(Employee.id).where(Employee.id != original_actor).order_by(Employee.id))
        request = LoanRequestService(db, LoanRequestRepository(db)).create(
            LoanRequestCreate(book_id=book_id, pickup_date=business_today()), client_id=client_id)
        copy_id = db.scalar(select(Copy.id).where(Copy.book_id == book_id, Copy.destination == DestinationType.DIDACTIC))
        circulation = CirculationService(db, CirculationRepository(db))
        loan_id = circulation.confirm_pickup(request.id, copy_id, original_actor)['id']
        circulation.confirm_return(loan_id, different_actor)
        actor = db.scalar(text("""
            SELECT employee_id FROM audit_logs WHERE entity_type='copies' AND entity_id=:id
            AND old_value->>'status'='BORROWED' AND new_value->>'status'='AVAILABLE'
            ORDER BY id DESC LIMIT 1
        """), {'id': str(copy_id)})
        assert actor == different_actor
        assert db.get(Loan, loan_id).employee_id == original_actor
