"""Acervo administrado pelo vendedor (Issue #151): reativação de obra e edição/conversão de exemplar
contra PostgreSQL descartável migrado pelo Alembic."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.controllers.copy_controller import get_copy_service
from app.core.exceptions import ApplicationError, BookWithoutActiveCopyError
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_book_service
from app.main import app
from app.models.domain import (
    AuditLog, Book, Copy, CopyStatus, DestinationType, Loan, LoanStatus, Profile, PurchaseReservation,
)
from app.repositories.book_repository import BookRepository
from app.repositories.copy_repository import CopyRepository
from app.repositories.sale_repository import SaleRepository
from app.schemas.book_schema import BookUpdate
from app.schemas.sale_schema import SaleCreate
from app.services.book_service import BookService
from app.services.copy_service import CopyService
from app.services.sale_service import SaleService
from test_book_lock_races_postgres import hold_book_lock, loan_op, run_behind_lock
from test_client_requests_postgres import records  # noqa: F401  (fixture)
from test_staff_desk_postgres import desk, new_user  # noqa: F401  (fixtures)
from test_v2_review import ready_purchase

BARCODE_PREFIX = 'AC-151-'


@pytest.fixture
def acervo(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    sessions = []

    def session():
        db = Session(engine)
        sessions.append(db)
        return db

    app.dependency_overrides[get_copy_service] = lambda: CopyService(CopyRepository(db := session()), db)
    app.dependency_overrides[get_book_service] = lambda: BookService(db=(db := session()), repository=BookRepository(db))
    state = NS(roles=['SELLER'], user_id=seller_id)
    app.dependency_overrides[get_current_user] = lambda: NS(id=state.user_id, role_codes=state.roles)
    yield NS(http=http, engine=engine, book_id=book_id, client_id=client_id, seller_id=seller_id,
             admin_id=seller_id, state=state)
    for db in sessions:
        db.close()


def add_copy(acervo, destination=DestinationType.DIDACTIC, price=None, **extra):
    with Session(acervo.engine) as db:
        db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(acervo.seller_id)})
        copy = Copy(book_id=acervo.book_id, barcode=BARCODE_PREFIX + uuid4().hex[:12], destination=destination,
                    sale_price=price, **extra)
        db.add(copy)
        db.commit()
        return copy.id


def load(acervo, copy_id):
    with Session(acervo.engine) as db:
        copy = db.get(Copy, copy_id)
        return NS(destination=copy.destination, sale_price=copy.sale_price, status=copy.status,
                  barcode=copy.barcode, condition=copy.condition, is_active=copy.is_active,
                  acquired_at=copy.acquired_at)


def patch_copy(acervo, copy_id, payload):
    return acervo.http.patch(f'/api/v1/copies/{copy_id}', json=payload)


def deactivate_whole_book(acervo):
    """Obra inativa sem exemplar ativo: o gatilho adiado só aceita isso com a obra inativa na mesma transação."""
    with Session(acervo.engine) as db:
        db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(acervo.seller_id)})
        db.execute(text('UPDATE books SET is_active = false WHERE id = :id'), {'id': acervo.book_id})
        db.execute(text('UPDATE copies SET is_active = false WHERE book_id = :id'), {'id': acervo.book_id})
        db.commit()


# --- papéis -------------------------------------------------------------------------------------

def test_seller_runs_every_catalog_operation_and_audit_records_the_seller(acervo):
    http = acervo.http
    assert http.patch(f'/api/v1/books/{acervo.book_id}', json={'genre': 'Romance'}).status_code == 200
    assert http.patch(f'/api/v1/books/{acervo.book_id}', json={'is_active': False}).status_code == 200
    reactivated = http.patch(f'/api/v1/books/{acervo.book_id}', json={'is_active': True})
    assert (reactivated.status_code, reactivated.json()['is_active']) == (200, True)

    created = http.post('/api/v1/copies/', json={
        'book_id': acervo.book_id, 'barcode': BARCODE_PREFIX + uuid4().hex[:12], 'destination': 'DIDACTIC'})
    assert created.status_code == 201
    copy_id = created.json()['id']
    assert patch_copy(acervo, copy_id, {'destination': 'COMMERCIAL', 'sale_price': '30.00'}).status_code == 200
    assert http.delete(f'/api/v1/copies/{copy_id}').status_code == 200
    with Session(acervo.engine) as db:
        updates = db.scalars(select(AuditLog).where(
            AuditLog.entity_type == 'copies', AuditLog.entity_id == str(copy_id), AuditLog.operation == 'UPDATE')).all()
        assert [entry.employee_id for entry in updates] == [acervo.seller_id]
        assert updates[0].old_value['destination'] == 'DIDACTIC' and updates[0].new_value['destination'] == 'COMMERCIAL'
        book_entries = db.scalars(select(AuditLog).where(
            AuditLog.entity_type == 'books', AuditLog.entity_id == str(acervo.book_id),
            AuditLog.operation == 'UPDATE')).all()
        assert book_entries and {entry.employee_id for entry in book_entries} == {acervo.seller_id}


def test_client_user_is_denied_every_catalog_operation(acervo):
    acervo.state.roles = ['USER']
    copy_id = add_copy(acervo)
    calls = [
        acervo.http.patch(f'/api/v1/books/{acervo.book_id}', json={'is_active': True}),
        acervo.http.post('/api/v1/copies/', json={'book_id': acervo.book_id, 'barcode': 'X', 'destination': 'DIDACTIC'}),
        patch_copy(acervo, copy_id, {'condition': 'Bom'}),
        acervo.http.delete(f'/api/v1/copies/{copy_id}'),
    ]
    assert [(call.status_code, call.json()['code']) for call in calls] == [(403, 'permission_denied')] * 4
    assert load(acervo, copy_id).condition is None


def test_inactive_employee_cannot_run_catalog_operations(acervo):
    copy_id = add_copy(acervo)
    with Session(acervo.engine) as db:
        db.get(Profile, acervo.seller_id).is_active = False
        db.commit()
    try:
        calls = [
            acervo.http.patch(f'/api/v1/books/{acervo.book_id}', json={'genre': 'Poesia'}),
            acervo.http.post('/api/v1/copies/', json={'book_id': acervo.book_id, 'barcode': 'Z', 'destination': 'DIDACTIC'}),
            patch_copy(acervo, copy_id, {'condition': 'Bom'}),
            acervo.http.delete(f'/api/v1/copies/{copy_id}'),
        ]
        assert [call.status_code for call in calls] == [403] * 4
        assert load(acervo, copy_id).condition is None
    finally:
        with Session(acervo.engine) as db:
            db.get(Profile, acervo.seller_id).is_active = True
            db.commit()


# --- reativação de obra --------------------------------------------------------------------------

def test_reactivation_without_active_copy_is_a_domain_error_and_changes_nothing(acervo):
    deactivate_whole_book(acervo)
    response = acervo.http.patch(f'/api/v1/books/{acervo.book_id}', json={'is_active': True})
    assert (response.status_code, response.json()['code']) == (409, 'book_without_active_copy')
    with Session(acervo.engine) as db:
        assert db.get(Book, acervo.book_id).is_active is False


def test_reactivation_with_an_active_copy_succeeds(acervo):
    deactivate_whole_book(acervo)
    with Session(acervo.engine) as db:
        db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(acervo.seller_id)})
        db.execute(text('UPDATE copies SET is_active = true WHERE id = (SELECT min(id) FROM copies WHERE book_id = :id)'),
                   {'id': acervo.book_id})
        db.commit()
    response = acervo.http.patch(f'/api/v1/books/{acervo.book_id}', json={'is_active': True})
    assert (response.status_code, response.json()['is_active']) == (200, True)
    with Session(acervo.engine) as db:
        assert db.get(Book, acervo.book_id).is_active is True


def test_database_trigger_is_mapped_to_the_domain_error_never_to_500(acervo):
    deactivate_whole_book(acervo)
    with Session(acervo.engine) as db:
        repository = BookRepository(db)
        repository.has_active_copy = lambda _id: True  # força o gatilho adiado a ser a última barreira
        with pytest.raises(BookWithoutActiveCopyError):
            BookService(db=db, repository=repository).update_book(
                acervo.book_id, BookUpdate(is_active=True), employee_id=acervo.seller_id)
    with Session(acervo.engine) as db:
        assert db.get(Book, acervo.book_id).is_active is False


# --- edição e conversão de exemplar --------------------------------------------------------------

def test_conversion_to_commercial_requires_a_positive_price(acervo):
    copy_id = add_copy(acervo)
    for payload in ({'destination': 'COMMERCIAL'}, {'destination': 'COMMERCIAL', 'sale_price': '0'}):
        response = patch_copy(acervo, copy_id, payload)
        assert (response.status_code, response.json()['code']) == (422, 'copy_sale_price_required')
    assert load(acervo, copy_id).destination == DestinationType.DIDACTIC
    response = patch_copy(acervo, copy_id, {'destination': 'COMMERCIAL', 'sale_price': '45.90'})
    body = response.json()
    assert (response.status_code, body['destination'], Decimal(str(body['sale_price']))) == (200, 'COMMERCIAL', Decimal('45.90'))
    assert body['barcode'] == load(acervo, copy_id).barcode and body['status'] == 'AVAILABLE'


def test_conversion_to_didactic_removes_the_price_and_didactic_cannot_carry_one(acervo):
    copy_id = add_copy(acervo, DestinationType.COMMERCIAL, 25)
    response = patch_copy(acervo, copy_id, {'destination': 'DIDACTIC'})
    assert (response.status_code, response.json()['sale_price'], response.json()['destination']) == (200, None, 'DIDACTIC')
    assert load(acervo, copy_id).sale_price is None
    # Preço informado junto da conversão para didático: contrato da API (422).
    with_price = patch_copy(acervo, copy_id, {'destination': 'DIDACTIC', 'sale_price': '10'})
    assert with_price.status_code == 422
    # Exemplar já didático que recebe preço sem converter: erro de domínio estável.
    without_destination = patch_copy(acervo, copy_id, {'sale_price': '10'})
    assert (without_destination.status_code, without_destination.json()['code']) == (422, 'copy_sale_price_not_allowed')


def test_price_of_a_commercial_copy_can_change_and_never_to_zero(acervo):
    copy_id = add_copy(acervo, DestinationType.COMMERCIAL, 25)
    assert patch_copy(acervo, copy_id, {'sale_price': '0'}).json()['code'] == 'copy_sale_price_required'
    ok = patch_copy(acervo, copy_id, {'sale_price': '31.50', 'condition': 'Usado', 'acquired_at': '2026-01-15'})
    assert ok.status_code == 200
    stored = load(acervo, copy_id)
    assert (stored.sale_price, stored.condition, str(stored.acquired_at)) == (Decimal('31.50'), 'Usado', '2026-01-15')


def test_barcode_is_immutable_and_invalid_payloads_are_rejected(acervo):
    copy_id = add_copy(acervo)
    before = load(acervo, copy_id)
    for payload in ({'barcode': 'OUTRO'}, {}, {'destination': None}, {'sale_price': '-1'}, {'status': 'SOLD'},
                    {'is_active': False}, {'book_id': 1}, {'condition': 'x' * 31}):
        assert patch_copy(acervo, copy_id, payload).status_code == 422, payload
    after = load(acervo, copy_id)
    assert (after.barcode, after.status, after.is_active) == (before.barcode, before.status, True)


def test_unknown_copy_returns_404(acervo):
    response = patch_copy(acervo, 2_000_000_000, {'condition': 'Bom'})
    assert (response.status_code, response.json()['code']) == (404, 'copy_not_found')


def test_borrowed_copy_cannot_be_edited(acervo):
    copy_id = add_copy(acervo)
    with Session(acervo.engine) as db:
        now = datetime.now(timezone.utc)
        db.add(Loan(client_id=acervo.client_id, copy_id=copy_id, employee_id=acervo.seller_id, loan_date=now,
                    due_date=now + timedelta(days=30), status=LoanStatus.OPEN))
        db.commit()
    assert load(acervo, copy_id).status == CopyStatus.BORROWED
    response = patch_copy(acervo, copy_id, {'destination': 'COMMERCIAL', 'sale_price': '20'})
    assert (response.status_code, response.json()['code']) == (409, 'copy_not_available')
    assert load(acervo, copy_id).destination == DestinationType.DIDACTIC


def test_sold_copy_cannot_be_edited(acervo):
    copy_id = add_copy(acervo, DestinationType.COMMERCIAL, 20)
    with Session(acervo.engine) as db:
        SaleService(SaleRepository(db), db).create_sale(
            SaleCreate(client_id=acervo.client_id, items=[{'copy_id': copy_id, 'unit_price': '20.00'}]),
            employee_id=acervo.seller_id)
    assert load(acervo, copy_id).status == CopyStatus.SOLD
    response = patch_copy(acervo, copy_id, {'destination': 'DIDACTIC'})
    assert (response.status_code, response.json()['code']) == (409, 'copy_not_available')
    assert load(acervo, copy_id).destination == DestinationType.COMMERCIAL


def test_copy_allocated_to_a_reservation_cannot_be_edited(acervo):
    with Session(acervo.engine) as db:
        ready_purchase(db, acervo.book_id, acervo.client_id)
        copy_id = db.scalar(select(PurchaseReservation.allocated_copy_id).where(
            PurchaseReservation.client_id == acervo.client_id, PurchaseReservation.allocated_copy_id.is_not(None)))
    assert copy_id is not None
    response = patch_copy(acervo, copy_id, {'destination': 'DIDACTIC'})
    body = response.json()
    assert (response.status_code, body['code']) == (409, 'copy_allocated')
    assert [reason['code'] for reason in body['details']['reasons']] == ['copy_allocated']
    assert load(acervo, copy_id).destination == DestinationType.COMMERCIAL


def test_inactive_copy_cannot_be_edited(acervo):
    copy_id = add_copy(acervo)  # a obra mantém outros exemplares ativos
    with Session(acervo.engine) as db:
        db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(acervo.seller_id)})
        db.execute(text('UPDATE copies SET is_active = false WHERE id = :id'), {'id': copy_id})
        db.commit()
    response = patch_copy(acervo, copy_id, {'condition': 'Bom'})
    assert (response.status_code, response.json()['code']) == (409, 'copy_inactive')


def test_no_op_edit_keeps_the_copy_and_writes_no_audit_entry(acervo):
    copy_id = add_copy(acervo, condition='Bom')
    with Session(acervo.engine) as db:
        before = db.query(AuditLog).filter(AuditLog.entity_type == 'copies', AuditLog.entity_id == str(copy_id)).count()
    assert patch_copy(acervo, copy_id, {'condition': 'Bom'}).status_code == 200
    with Session(acervo.engine) as db:
        assert db.query(AuditLog).filter(AuditLog.entity_type == 'copies', AuditLog.entity_id == str(copy_id)).count() == before


# --- concorrência: edição x empréstimo direto, ordem forçada pelo lock do livro ------------------

def edit_op(acervo, copy_id, payload):
    def run():
        with Session(acervo.engine) as db:
            from app.schemas.copy_schema import CopyUpdate
            try:
                CopyService(CopyRepository(db), db).update_copy(copy_id, CopyUpdate(**payload), acervo.seller_id)
                return 'ok'
            except ApplicationError as error:
                return error.code
    return run


def test_edit_waits_for_an_uncommitted_loan_and_is_then_blocked(acervo):
    copy_id = add_copy(acervo)
    holder = hold_book_lock(acervo)
    now = datetime.now(timezone.utc)
    holder.add(Loan(client_id=acervo.client_id, copy_id=copy_id, employee_id=acervo.seller_id, loan_date=now,
                    due_date=now + timedelta(days=30), status=LoanStatus.OPEN))
    holder.flush()
    [result] = run_behind_lock(acervo, holder, edit_op(acervo, copy_id, {'destination': 'COMMERCIAL', 'sale_price': 20}))
    assert result == 'copy_not_available'
    stored = load(acervo, copy_id)
    assert (stored.destination, stored.status) == (DestinationType.DIDACTIC, CopyStatus.BORROWED)


def test_loan_waits_for_an_uncommitted_conversion_and_is_refused(acervo):
    copy_id = add_copy(acervo)
    holder = hold_book_lock(acervo)
    holder.execute(text("UPDATE copies SET destination = 'COMMERCIAL', sale_price = 20 WHERE id = :id"), {'id': copy_id})
    [result] = run_behind_lock(acervo, holder, loan_op(acervo, copy_id))
    assert result in ('copy_not_for_loan', 409)
    with Session(acervo.engine) as db:
        assert db.query(Loan).filter(Loan.copy_id == copy_id).count() == 0
        assert db.get(Copy, copy_id).destination == DestinationType.COMMERCIAL


def test_two_concurrent_edits_are_serialized_and_both_apply_in_order(acervo):
    copy_id = add_copy(acervo)
    holder = hold_book_lock(acervo)
    results = run_behind_lock(acervo, holder, edit_op(acervo, copy_id, {'condition': 'Novo'}),
                              edit_op(acervo, copy_id, {'acquired_at': '2026-02-01'}))
    assert results == ['ok', 'ok']
    stored = load(acervo, copy_id)
    assert (stored.condition, str(stored.acquired_at)) == ('Novo', '2026-02-01')


def test_database_guard_still_refuses_destination_change_without_an_authorized_actor(acervo):
    """O gatilho guard_copy_integrity aceita SELLER, STOCK_KEEPER e ADMINISTRATOR; mudança sem funcionário responsável continua barrada."""
    copy_id = add_copy(acervo)
    with Session(acervo.engine) as db:
        with pytest.raises(Exception, match='Changing destination requires'):
            db.execute(text("UPDATE copies SET destination = 'COMMERCIAL', sale_price = 9 WHERE id = :id"), {'id': copy_id})
    assert load(acervo, copy_id).destination == DestinationType.DIDACTIC
