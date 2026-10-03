"""Exclusão de exemplar e bloqueios de inativação (Issue #135) contra PostgreSQL descartável migrado pelo Alembic."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.controllers.copy_controller import get_copy_service
from app.core.exceptions import ApplicationError
from app.dependencies.authentication import get_current_user
from app.main import app
from app.models.domain import (
    AuditLog, Book, Copy, CopyStatus, DestinationType, Loan, LoanStatus, PurchaseReservation, ReservationStatus,
    Sale, SaleItem, SaleStatus,
)
from app.models.loan_request import LoanRequest
from app.repositories.book_repository import BookRepository
from app.repositories.client_pendency_repository import ClientPendencyRepository
from app.repositories.copy_repository import CopyRepository
from app.repositories.loan_repository import LoanRepository
from app.repositories.loan_request_repository import LoanRequestRepository
from app.schemas.book_schema import BookUpdate
from app.schemas.copy_schema import CopyCreate
from app.schemas.loan_request_schema import LoanRequestCreate
from app.schemas.loan_schema import LoanCreate
from app.services.book_service import BookService
from app.services.client_pendency_service import ClientPendencyService
from app.services.copy_service import CopyService
from app.services.loan_request_service import LoanRequestService, business_today
from app.services.loan_service import LoanService
from test_client_requests_postgres import records  # noqa: F401  (fixture)
from test_staff_desk_postgres import commercial_copy, desk, didactic_copy, new_user  # noqa: F401  (fixtures)
from test_v2_review import ready_purchase, second_client


@pytest.fixture
def api(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    with Session(engine) as db:
        admin_id = new_user(db, 'ADMINISTRATOR', 'Administrador exclusão')
    sessions = []

    def service():
        db = Session(engine)
        sessions.append(db)
        return CopyService(CopyRepository(db), db)

    app.dependency_overrides[get_copy_service] = service
    app.dependency_overrides[get_current_user] = lambda: NS(id=admin_id, role_codes=['ADMINISTRATOR'])
    yield NS(http=http, engine=engine, book_id=book_id, client_id=client_id, admin_id=admin_id, service=service)
    for db in sessions:
        db.close()


def add_copy(api, destination=DestinationType.DIDACTIC):
    with Session(api.engine) as db:
        return CopyService(CopyRepository(db), db).create_new_copy(
            CopyCreate(book_id=api.book_id, barcode='DEL-135-' + uuid4().hex[:12], destination=destination,
                       sale_price=None if destination == DestinationType.DIDACTIC else 20),
            actor_id=api.admin_id).id


def open_loan(db, copy_id, client_id, employee_id):
    now = datetime.now(timezone.utc)
    loan = Loan(client_id=client_id, copy_id=copy_id, employee_id=employee_id, loan_date=now,
                due_date=now + timedelta(days=30), status=LoanStatus.OPEN)
    db.add(loan)
    db.flush()
    return loan


def close_loan(db, loan):
    loan.status, loan.returned_at = LoanStatus.RETURNED, datetime.now(timezone.utc)
    db.flush()


def remove(api, copy_id):
    return api.http.delete(f'/api/v1/copies/{copy_id}')


def exists(api, copy_id):
    with Session(api.engine) as db:
        return db.get(Copy, copy_id) is not None


def test_delete_without_history_removes_copy_and_audits_the_employee(api):
    copy_id = add_copy(api)
    with Session(api.engine) as db:
        barcode = db.get(Copy, copy_id).barcode
    response = remove(api, copy_id)
    assert response.status_code == 200
    assert response.json() == {'id': copy_id, 'book_id': api.book_id, 'barcode': barcode, 'deleted': True}
    assert not exists(api, copy_id)
    with Session(api.engine) as db:
        entry = db.scalar(select(AuditLog).where(
            AuditLog.entity_type == 'copies', AuditLog.entity_id == str(copy_id), AuditLog.operation == 'DELETE'))
        assert entry.employee_id == api.admin_id
        assert entry.old_value['barcode'] == barcode and entry.new_value is None
    assert remove(api, copy_id).status_code == 404  # segunda tentativa: já não existe


def test_delete_unknown_copy_returns_404(api):
    response = remove(api, 2_000_000_000)
    assert (response.status_code, response.json()['code']) == (404, 'copy_not_found')


def test_open_loan_blocks_deletion_with_reasons_and_keeps_the_copy(api):
    copy_id = add_copy(api)
    with Session(api.engine) as db:
        open_loan(db, copy_id, api.client_id, api.admin_id)
        db.commit()
    response = remove(api, copy_id)
    body = response.json()
    assert (response.status_code, body['code']) == (409, 'copy_not_available')
    assert [r['code'] for r in body['details']['reasons']] == ['copy_not_available', 'copy_has_history']
    assert body['details']['history']['loans'] == 1
    assert exists(api, copy_id)


def test_closed_loan_still_blocks_deletion_as_history(api):
    copy_id = add_copy(api)
    with Session(api.engine) as db:
        close_loan(db, open_loan(db, copy_id, api.client_id, api.admin_id))
        db.commit()
        assert db.get(Copy, copy_id).status == CopyStatus.AVAILABLE
    body = remove(api, copy_id).json()
    assert body['code'] == 'copy_has_history'
    assert [r['code'] for r in body['details']['reasons']] == ['copy_has_history']
    assert exists(api, copy_id)


def test_sale_blocks_deletion_pending_as_history_and_confirmed_as_unavailable(api):
    pending = add_copy(api, DestinationType.COMMERCIAL)
    confirmed = add_copy(api, DestinationType.COMMERCIAL)
    with Session(api.engine) as db:
        for copy_id, status in ((pending, SaleStatus.PENDING), (confirmed, SaleStatus.PENDING)):
            sale = Sale(employee_id=api.admin_id, total_amount=20, status=SaleStatus.PENDING)
            db.add(sale); db.flush()
            db.add(SaleItem(sale_id=sale.id, copy_id=copy_id, unit_price=20)); db.flush()
            if copy_id == confirmed:
                sale.status = SaleStatus.CONFIRMED; db.flush()
        db.commit()
        assert db.get(Copy, confirmed).status == CopyStatus.SOLD
    first = remove(api, pending).json()
    assert (first['code'], first['details']['history']['sales']) == ('copy_has_history', 1)
    second = remove(api, confirmed).json()
    assert second['code'] == 'copy_not_available'
    assert exists(api, pending) and exists(api, confirmed)


def test_allocated_purchase_reservation_blocks_deletion(api):
    with Session(api.engine) as db:
        ready_purchase(db, api.book_id, api.client_id)
        copy_id = db.scalar(select(PurchaseReservation.allocated_copy_id).where(
            PurchaseReservation.book_id == api.book_id, PurchaseReservation.status == ReservationStatus.NOTIFIED))
    body = remove(api, copy_id).json()
    assert body['code'] == 'copy_has_history'
    assert body['details']['history']['purchase_reservations'] == 1
    assert exists(api, copy_id)


def test_last_active_copy_of_an_active_book_is_blocked_but_not_after_the_book_is_inactive(api):
    with Session(api.engine) as db:
        ids = list(db.scalars(select(Copy.id).where(Copy.book_id == api.book_id)))
    assert len(ids) == 2
    assert remove(api, ids[0]).status_code == 200
    blocked = remove(api, ids[1])
    assert (blocked.status_code, blocked.json()['code']) == (409, 'last_active_copy')
    assert exists(api, ids[1])
    with Session(api.engine) as db:
        BookService(db=db, repository=BookRepository(db)).update_book(
            api.book_id, BookUpdate(is_active=False), employee_id=api.admin_id)
    assert remove(api, ids[1]).status_code == 200


def test_database_foreign_key_is_treated_as_a_block_never_a_500(api, monkeypatch):
    copy_id = add_copy(api)
    with Session(api.engine) as db:
        close_loan(db, open_loan(db, copy_id, api.client_id, api.admin_id))
        db.commit()
    # A checagem de histórico "não enxerga" o vínculo; a FK RESTRICT do banco barra o DELETE.
    monkeypatch.setattr(CopyRepository, 'history_counts',
                        lambda self, _id: {'loans': 0, 'sales': 0, 'purchase_reservations': 0, 'requests': 0})
    response = remove(api, copy_id)
    assert (response.status_code, response.json()['code']) == (409, 'copy_has_history')
    assert exists(api, copy_id)
    with Session(api.engine) as db:
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.entity_type == 'copies', AuditLog.entity_id == str(copy_id), AuditLog.operation == 'DELETE')) == 0


def test_persistence_failure_rolls_back_and_returns_stable_500(api, monkeypatch):
    from sqlalchemy.exc import OperationalError
    copy_id = add_copy(api)

    def boom(self, copy):
        raise OperationalError('DELETE', {}, Exception('connection lost'))

    monkeypatch.setattr(CopyRepository, 'delete_copy', boom)
    response = remove(api, copy_id)
    assert (response.status_code, response.json()['code']) == (500, 'copy_delete_persistence_error')
    assert exists(api, copy_id)


def test_concurrent_deletes_of_the_same_copy_yield_one_200_and_one_404(api):
    copy_id = add_copy(api)
    barrier = Barrier(2)

    def attempt(_):
        service = api.service()
        barrier.wait(timeout=10)
        try:
            service.delete_copy(copy_id, api.admin_id)
            return 200
        except ApplicationError as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(attempt, range(2)))
    assert results == [200, 404]
    assert not exists(api, copy_id)


def test_delete_racing_a_direct_loan_never_leaves_a_loan_without_its_copy(api):
    copy_id = add_copy(api)
    barrier = Barrier(2)

    def delete_attempt():
        service = api.service()
        barrier.wait(timeout=10)
        try:
            service.delete_copy(copy_id, api.admin_id)
            return 'deleted'
        except ApplicationError as error:
            return error.code

    def loan_attempt():
        with Session(api.engine) as db:
            service = LoanService(LoanRepository(db), db, ClientPendencyService(db=db, repository=ClientPendencyRepository(db)))
            barrier.wait(timeout=10)
            try:
                service.create_loan(LoanCreate(client_id=api.client_id, copy_id=copy_id), employee_id=api.admin_id)
                return 'loaned'
            except Exception as error:  # HTTPException do fluxo de empréstimo
                return getattr(error, 'status_code', 500)

    with ThreadPoolExecutor(max_workers=2) as pool:
        deleting, loaning = pool.submit(delete_attempt), pool.submit(loan_attempt)
        deleted, loaned = deleting.result(), loaning.result()
    assert (deleted, loaned) in {('deleted', 404), ('copy_not_available', 'loaned')}, (deleted, loaned)
    with Session(api.engine) as db:
        assert (db.get(Copy, copy_id) is None) == (deleted == 'deleted')
        assert db.scalar(select(func.count()).select_from(Loan).where(Loan.copy_id == copy_id)) == (0 if deleted == 'deleted' else 1)


# ---- inativação da obra ----------------------------------------------------------------------

def inactivate(api, book_id=None):
    with Session(api.engine) as db:
        return BookService(db=db, repository=BookRepository(db)).update_book(
            book_id or api.book_id, BookUpdate(is_active=False), employee_id=api.admin_id)


def assert_blocked(api, **counts):
    with pytest.raises(ApplicationError) as blocked:
        inactivate(api)
    assert (blocked.value.status_code, blocked.value.code) == (409, 'book_has_active_operations')
    expected = {'open_loans': 0, 'pending_loan_requests': 0, 'purchase_reservations': 0, **counts}
    assert blocked.value.details['counts'] == expected
    with Session(api.engine) as db:
        assert db.get(Book, api.book_id).is_active is True
    return blocked.value


def test_inactivation_blocked_by_open_loan_of_any_copy_returns_links(api):
    with Session(api.engine) as db:
        copy = didactic_copy(db, api.book_id)
        barcode = copy.barcode
        open_loan(db, copy.id, api.client_id, api.admin_id)
        db.commit()
    error = assert_blocked(api, open_loans=1)
    link = error.details['links'][0]
    assert (link['type'], link['copy_barcode']) == ('open_loan', barcode)
    assert link['client_name'] == 'Teste Cliente'


def test_inactivation_blocked_by_pending_pickup_request(api):
    with Session(api.engine) as db:
        LoanRequestService(db, LoanRequestRepository(db)).create(
            LoanRequestCreate(book_id=api.book_id, pickup_date=business_today()), client_id=api.client_id)
    error = assert_blocked(api, pending_loan_requests=1)
    assert error.details['links'][0]['type'] == 'pending_loan_request'


def test_inactivation_blocked_by_waiting_purchase_reservation(api):
    with Session(api.engine) as db:
        open_loan(db, commercial_copy(db, api.book_id).id, api.client_id, api.admin_id)
        other = second_client(db)
        db.add(PurchaseReservation(client_id=other, book_id=api.book_id, status=ReservationStatus.WAITING, queue_position=1))
        db.commit()
    assert_blocked(api, open_loans=1, purchase_reservations=1)


def test_inactivation_blocked_by_notified_purchase_reservation(api):
    with Session(api.engine) as db:
        ready_purchase(db, api.book_id, api.client_id)
    error = assert_blocked(api, purchase_reservations=1)
    assert error.details['links'][0]['type'] == 'purchase_reservation'
    assert error.details['links'][0]['copy_barcode'] is not None


def test_inactivation_allowed_when_only_history_remains_and_audits_the_employee(api):
    with Session(api.engine) as db:
        close_loan(db, open_loan(db, didactic_copy(db, api.book_id).id, api.client_id, api.admin_id))
        db.commit()
    result = inactivate(api)
    assert result.is_active is False
    with Session(api.engine) as db:
        assert db.get(Book, api.book_id).is_active is False
        assert db.scalar(select(func.count()).select_from(Loan).where(Loan.client_id == api.client_id)) == 1
        entry = db.scalars(select(AuditLog).where(
            AuditLog.entity_type == 'books', AuditLog.entity_id == str(api.book_id),
            AuditLog.operation == 'UPDATE').order_by(AuditLog.id.desc())).first()
        assert entry.employee_id == api.admin_id and entry.new_value['is_active'] is False


def test_other_book_updates_are_not_blocked_by_operations(api):
    with Session(api.engine) as db:
        open_loan(db, didactic_copy(db, api.book_id).id, api.client_id, api.admin_id)
        db.commit()
    with Session(api.engine) as db:
        result = BookService(db=db, repository=BookRepository(db)).update_book(
            api.book_id, BookUpdate(genre='Romance'), employee_id=api.admin_id)
        assert result.genre == 'Romance' and result.is_active is True


def test_inactivation_racing_a_pending_request_never_leaves_an_inactive_book_with_a_pending_request(api):
    barrier = Barrier(2)

    def request():
        with Session(api.engine) as db:
            barrier.wait(timeout=10)
            try:
                LoanRequestService(db, LoanRequestRepository(db)).create(
                    LoanRequestCreate(book_id=api.book_id, pickup_date=business_today()), client_id=api.client_id)
                return 'requested'
            except ApplicationError as error:
                return error.code

    def deactivate():
        with Session(api.engine) as db:
            barrier.wait(timeout=10)
            try:
                BookService(db=db, repository=BookRepository(db)).update_book(
                    api.book_id, BookUpdate(is_active=False), employee_id=api.admin_id)
                return 'inactivated'
            except ApplicationError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        requesting, deactivating = pool.submit(request), pool.submit(deactivate)
        requested, deactivated = requesting.result(), deactivating.result()
    # A solicitação trava o livro; ou ela vem antes e bloqueia a inativação, ou depois e é recusada (obra inativa).
    assert (requested, deactivated) in {
        ('requested', 'book_has_active_operations'), ('book_not_found', 'inactivated'),
    }, (requested, deactivated)
    with Session(api.engine) as db:
        pending = db.scalar(select(func.count()).select_from(LoanRequest).where(
            LoanRequest.book_id == api.book_id, LoanRequest.loan_id.is_(None)))
        assert pending == (1 if deactivated == 'book_has_active_operations' else 0)
