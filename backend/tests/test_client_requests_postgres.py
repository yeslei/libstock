"""Run against an isolated database migrated by Alembic.

Set LIBSTOCK_V2_TEST_DATABASE_URL explicitly; never touches the application DB.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.models.domain import Book, Client, Copy, DestinationType, Employee, Profile, Role, UserRole
from app.models.user import User
from app.repositories.loan_request_repository import LoanRequestRepository
from app.repositories.purchase_request_repository import PurchaseRequestRepository
from app.schemas.loan_request_schema import LoanRequestCreate
from app.schemas.purchase_request_schema import PurchaseRequestCreate
from app.services.loan_request_service import LoanRequestService, business_today
from app.services.purchase_request_service import PurchaseRequestService


@pytest.fixture
def records():
    url = os.environ.get('LIBSTOCK_V2_TEST_DATABASE_URL')
    if not url:
        pytest.skip('requires isolated migrated PostgreSQL test database')
    engine = create_engine(url)
    with Session(engine) as db:
        admin_role = db.scalar(select(Role).where(Role.code == 'ADMINISTRATOR'))
        user_role = db.scalar(select(Role).where(Role.code == 'USER'))
        admin = User(name='Teste Admin', email=f'{uuid4().hex}@test.invalid', password_hash='test')
        client = User(name='Teste Cliente', email=f'{uuid4().hex}@test.invalid', password_hash='test')
        db.add_all([admin, client]); db.flush()
        db.add_all([Profile(id=admin.id), Profile(id=client.id)]); db.flush()
        db.add_all([Employee(id=admin.id, role_id=admin_role.id, employee_code=uuid4().hex),
                    Client(id=client.id), UserRole(user_id=admin.id, role_id=admin_role.id),
                    UserRole(user_id=client.id, role_id=user_role.id)])
        db.flush()
        db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(admin.id)})
        book = Book(title='Livro integração', author='Autor')
        db.add(book); db.flush()
        db.add_all([Copy(book_id=book.id, barcode=uuid4().hex, destination=DestinationType.DIDACTIC),
                    Copy(book_id=book.id, barcode=uuid4().hex, destination=DestinationType.COMMERCIAL, sale_price=25)])
        db.commit()
        book_id, client_id = book.id, client.id
    yield engine, book_id, client_id
    engine.dispose()


@pytest.mark.parametrize('kind', ['loan', 'purchase'])
def test_concurrent_duplicate_requests_are_serialized(records, kind):
    engine, book_id, client_id = records
    barrier = Barrier(2)

    def submit():
        with Session(engine) as db:
            if kind == 'loan':
                service = LoanRequestService(db, LoanRequestRepository(db))
                payload = LoanRequestCreate(book_id=book_id, pickup_date=business_today())
            else:
                service = PurchaseRequestService(db, PurchaseRequestRepository(db))
                payload = PurchaseRequestCreate(book_id=book_id, pickup_date=business_today())
            barrier.wait(timeout=10)
            try:
                service.create(payload, client_id=client_id)
                return 201
            except ApplicationError as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: submit(), range(2)))
    assert sorted(results) == [201, 409]
    table = 'loan_requests' if kind == 'loan' else 'purchase_requests'
    with engine.connect() as connection:
        assert connection.scalar(text(f'SELECT count(*) FROM {table} WHERE book_id = :id'), {'id': book_id}) == 1
        assert connection.scalar(text("SELECT count(*) FROM audit_logs WHERE entity_type = :table AND new_value->>'book_id' = :id"), {'table': table, 'id': str(book_id)}) == 1
        assert connection.scalar(text("SELECT count(*) FROM copies WHERE book_id = :id AND status = 'AVAILABLE'"), {'id': book_id}) == 2


def test_repository_limits_purchase_to_commercial_and_loan_to_didactic(records):
    engine, book_id, _ = records
    with Session(engine) as db:
        assert LoanRequestRepository(db).lock_available_copy(book_id).destination == DestinationType.DIDACTIC
        db.rollback()
        assert PurchaseRequestRepository(db).lock_available_copy(book_id).destination == DestinationType.COMMERCIAL


def test_transaction_rolls_back_request_and_audit_on_commit_failure(records):
    engine, book_id, client_id = records
    from sqlalchemy.exc import SQLAlchemyError
    class FailedCommitSession(Session):
        def commit(self):
            raise SQLAlchemyError('forced failure before commit')
    with FailedCommitSession(engine) as db:
        with pytest.raises(ApplicationError):
            LoanRequestService(db, LoanRequestRepository(db)).create(
                LoanRequestCreate(book_id=book_id, pickup_date=business_today()), client_id=client_id)
    with engine.connect() as connection:
        assert connection.scalar(text('SELECT count(*) FROM loan_requests WHERE book_id = :id'), {'id': book_id}) == 0
        assert connection.scalar(text("SELECT count(*) FROM audit_logs WHERE entity_type = 'loan_requests' AND new_value->>'book_id' = :id"), {'id': str(book_id)}) == 0
