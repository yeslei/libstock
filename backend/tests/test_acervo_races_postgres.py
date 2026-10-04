"""Corridas com ordem forçada pelo lock do livro e barreiras do banco no acervo (Issue #151)
contra PostgreSQL descartável migrado pelo Alembic."""
from datetime import timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.core.exceptions import ApplicationError, CopyUpdateBlockedError, PermissionDeniedError
from app.models.domain import (
    Book, Copy, CopyStatus, DestinationType, Loan, LoanStatus, PurchaseReservation, SaleItem, UserRole,
)
from app.repositories.book_repository import BookRepository
from app.repositories.copy_repository import CopyRepository
from app.repositories.loan_request_repository import LoanRequestRepository
from app.schemas.book_schema import BookUpdate
from app.schemas.copy_schema import CopyUpdate
from app.schemas.loan_request_schema import LoanRequestCreate
from app.services.book_service import BookService
from app.services.copy_service import CopyService
from app.services.loan_request_service import LoanRequestService, business_today
from test_acervo_seller_postgres import acervo, add_copy, deactivate_whole_book, load, patch_copy  # noqa: F401
from test_book_lock_races_postgres import hold_book_lock, run_behind_lock, sale_op
from test_client_requests_postgres import records  # noqa: F401  (fixture)
from test_staff_desk_postgres import desk, new_user  # noqa: F401  (fixtures)
from test_v2_review import ready_purchase


def book_op(acervo, payload):
    def run():
        with Session(acervo.engine) as db:
            try:
                BookService(db=db, repository=BookRepository(db)).update_book(
                    acervo.book_id, BookUpdate(**payload), employee_id=acervo.seller_id)
                return 'ok'
            except ApplicationError as error:
                return error.code
    return run


def delete_op(acervo, copy_id):
    def run():
        with Session(acervo.engine) as db:
            try:
                CopyService(CopyRepository(db), db).delete_copy(copy_id, acervo.seller_id)
                return 'ok'
            except ApplicationError as error:
                return error.code
    return run


def book_active(acervo):
    with Session(acervo.engine) as db:
        return db.get(Book, acervo.book_id).is_active


# --- 1. decisão de ativar/inativar usa o valor travado -------------------------------------------

def test_reactivation_waits_for_an_uncommitted_inactivation_and_uses_the_locked_value(acervo):  # noqa: F811
    holder = hold_book_lock(acervo)
    holder.execute(text('UPDATE books SET is_active = false WHERE id = :id'), {'id': acervo.book_id})
    [result] = run_behind_lock(acervo, holder, book_op(acervo, {'is_active': True}))
    assert result == 'ok'
    assert book_active(acervo) is True  # a reativação não foi perdida por leitura velha


def test_inactivation_waits_for_an_uncommitted_reactivation_and_uses_the_locked_value(acervo):  # noqa: F811
    deactivate_whole_book(acervo)
    with Session(acervo.engine) as db:
        db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(acervo.seller_id)})
        db.execute(text('UPDATE copies SET is_active = true WHERE book_id = :id'), {'id': acervo.book_id})
        db.commit()
    holder = hold_book_lock(acervo)
    holder.execute(text('UPDATE books SET is_active = true WHERE id = :id'), {'id': acervo.book_id})
    [result] = run_behind_lock(acervo, holder, book_op(acervo, {'is_active': False}))
    assert result == 'ok'
    assert book_active(acervo) is False


# --- 3. outras corridas ----------------------------------------------------------------------------

def test_direct_sale_waits_for_an_uncommitted_conversion_to_didactic_and_is_refused(acervo):  # noqa: F811
    copy_id = add_copy(acervo, DestinationType.COMMERCIAL, 20)
    holder = hold_book_lock(acervo)
    holder.execute(text("UPDATE copies SET destination = 'DIDACTIC', sale_price = NULL WHERE id = :id"), {'id': copy_id})
    [result] = run_behind_lock(acervo, holder, sale_op(acervo, copy_id))
    assert result != 'ok'
    stored = load(acervo, copy_id)
    assert (stored.destination, stored.status) == (DestinationType.DIDACTIC, CopyStatus.AVAILABLE)
    with Session(acervo.engine) as db:
        assert db.query(SaleItem).filter(SaleItem.copy_id == copy_id).count() == 0


def test_purchase_request_waits_for_an_uncommitted_conversion_and_is_refused_without_reservation(acervo):  # noqa: F811
    with Session(acervo.engine) as db:
        commercial = db.scalar(select(Copy.id).where(
            Copy.book_id == acervo.book_id, Copy.destination == DestinationType.COMMERCIAL))
    holder = hold_book_lock(acervo)
    holder.execute(text("UPDATE copies SET destination = 'DIDACTIC', sale_price = NULL WHERE id = :id"), {'id': commercial})

    def request():
        with Session(acervo.engine) as db:
            try:
                ready_purchase(db, acervo.book_id, acervo.client_id)
                return 'ok'
            except ApplicationError as error:
                return error.code

    [result] = run_behind_lock(acervo, holder, request)
    assert result == 'purchase_unavailable'  # nenhum exemplar comercial sobrou para atender a solicitacao
    with Session(acervo.engine) as db:
        assert db.query(PurchaseReservation).filter(PurchaseReservation.client_id == acervo.client_id).count() == 0
        assert db.get(Copy, commercial).destination == DestinationType.DIDACTIC


def test_conversion_waits_for_an_uncommitted_allocation_and_is_blocked(acervo):  # noqa: F811
    with Session(acervo.engine) as db:
        commercial = db.scalar(select(Copy.id).where(
            Copy.book_id == acervo.book_id, Copy.destination == DestinationType.COMMERCIAL))
    holder = hold_book_lock(acervo)
    holder.execute(text(
        "INSERT INTO purchase_reservations (client_id, book_id, allocated_copy_id, status, queue_position, notified_at) "
        "VALUES (:c, :b, :copy, 'NOTIFIED', 1, now())"), {'c': acervo.client_id, 'b': acervo.book_id, 'copy': commercial})
    from test_acervo_seller_postgres import edit_op
    [result] = run_behind_lock(acervo, holder, edit_op(acervo, commercial, {'destination': 'DIDACTIC'}))
    assert result == 'copy_allocated'
    assert load(acervo, commercial).destination == DestinationType.COMMERCIAL


def only_active_copy(acervo):
    """Obra inativa com exatamente um exemplar ativo; devolve o id dele."""
    deactivate_whole_book(acervo)
    with Session(acervo.engine) as db:
        keep = db.scalar(select(Copy.id).where(Copy.book_id == acervo.book_id).order_by(Copy.id))
        db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(acervo.seller_id)})
        db.execute(text('UPDATE copies SET is_active = true WHERE id = :id'), {'id': keep})
        db.commit()
    return keep


def test_reactivation_waits_for_an_uncommitted_delete_of_the_only_active_copy(acervo):  # noqa: F811
    keep = only_active_copy(acervo)
    holder = hold_book_lock(acervo)
    holder.execute(text('DELETE FROM copies WHERE id = :id'), {'id': keep})
    [result] = run_behind_lock(acervo, holder, book_op(acervo, {'is_active': True}))
    assert result == 'book_without_active_copy'
    assert book_active(acervo) is False


def test_delete_of_the_only_active_copy_waits_for_an_uncommitted_reactivation_and_is_blocked(acervo):  # noqa: F811
    keep = only_active_copy(acervo)
    holder = hold_book_lock(acervo)
    holder.execute(text('UPDATE books SET is_active = true WHERE id = :id'), {'id': acervo.book_id})
    [result] = run_behind_lock(acervo, holder, delete_op(acervo, keep))
    assert result == 'last_active_copy'
    with Session(acervo.engine) as db:
        assert db.get(Copy, keep) is not None
    assert book_active(acervo) is True


# --- 5. último didático livre com solicitação de retirada pendente --------------------------------

def pending_pickup(acervo):
    with Session(acervo.engine) as db:
        LoanRequestService(db, LoanRequestRepository(db)).create(
            LoanRequestCreate(book_id=acervo.book_id, pickup_date=business_today()), client_id=acervo.client_id)


def only_free_didactic(acervo):
    with Session(acervo.engine) as db:
        return db.scalar(select(Copy.id).where(Copy.book_id == acervo.book_id, Copy.destination == DestinationType.DIDACTIC))


def test_last_free_didactic_copy_cannot_become_commercial_while_a_pickup_request_is_pending(acervo):  # noqa: F811
    pending_pickup(acervo)
    copy_id = only_free_didactic(acervo)
    response = patch_copy(acervo, copy_id, {'destination': 'COMMERCIAL', 'sale_price': '30'})
    assert (response.status_code, response.json()['code']) == (409, 'copy_needed_for_requests')
    assert load(acervo, copy_id).destination == DestinationType.DIDACTIC
    # Outras edições do mesmo exemplar continuam permitidas.
    assert patch_copy(acervo, copy_id, {'condition': 'Bom'}).status_code == 200


def test_conversion_is_allowed_when_another_free_didactic_copy_remains(acervo):  # noqa: F811
    pending_pickup(acervo)
    copy_id = only_free_didactic(acervo)
    add_copy(acervo)
    assert patch_copy(acervo, copy_id, {'destination': 'COMMERCIAL', 'sale_price': '30'}).status_code == 200


def test_conversion_waits_for_an_uncommitted_loan_request_and_is_then_blocked(acervo):  # noqa: F811
    copy_id = only_free_didactic(acervo)
    holder = hold_book_lock(acervo)
    holder.execute(text(
        "INSERT INTO loan_requests (client_id, book_id, pickup_date, due_date, status) "
        "VALUES (:c, :b, current_date, current_date + interval '1 month', 'PENDING')"), {'c': acervo.client_id, 'b': acervo.book_id})
    from test_acervo_seller_postgres import edit_op
    [result] = run_behind_lock(acervo, holder, edit_op(acervo, copy_id, {'destination': 'COMMERCIAL', 'sale_price': 30}))
    assert result == 'copy_needed_for_requests'
    assert load(acervo, copy_id).destination == DestinationType.DIDACTIC


# --- 2 e 4. barreiras do banco furando a pré-checagem do service ----------------------------------

def roleless_employee(acervo):
    with Session(acervo.engine) as db:
        user_id = new_user(db, 'SELLER', 'Sem papel de acervo')
        user_role = db.scalar(text("SELECT id FROM roles WHERE code = 'USER'"))
        db.execute(text('UPDATE user_roles SET role_id = :r WHERE user_id = :id'), {'r': user_role, 'id': user_id})
        db.execute(text('UPDATE employees SET role_id = :r WHERE id = :id'), {'r': user_role, 'id': user_id})
        db.commit()
    return user_id


def test_trigger_refuses_destination_change_by_an_employee_without_an_authorized_role(acervo):  # noqa: F811
    copy_id = add_copy(acervo)
    actor = roleless_employee(acervo)
    with Session(acervo.engine) as db:
        db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(actor)})
        with pytest.raises(Exception) as raised:
            db.execute(text("UPDATE copies SET destination = 'COMMERCIAL', sale_price = 9 WHERE id = :id"), {'id': copy_id})
        assert raised.value.orig.sqlstate == 'LS001'
    assert load(acervo, copy_id).destination == DestinationType.DIDACTIC


def test_service_maps_the_role_trigger_to_403_without_any_precheck(acervo):  # noqa: F811
    copy_id = add_copy(acervo)
    actor = roleless_employee(acervo)
    with Session(acervo.engine) as db:
        with pytest.raises(PermissionDeniedError):
            CopyService(CopyRepository(db), db).update_copy(
                copy_id, CopyUpdate(destination=DestinationType.COMMERCIAL, sale_price=9), actor)
    assert load(acervo, copy_id).destination == DestinationType.DIDACTIC


def test_service_maps_the_availability_trigger_to_409_when_the_precheck_is_bypassed(acervo):  # noqa: F811
    copy_id = add_copy(acervo)
    with Session(acervo.engine) as db:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        db.add(Loan(client_id=acervo.client_id, copy_id=copy_id, employee_id=acervo.seller_id, loan_date=now,
                    due_date=now + timedelta(days=30), status=LoanStatus.OPEN))
        db.commit()
    with Session(acervo.engine) as db:
        repository = CopyRepository(db)
        original = repository.lock_copy

        def spoofed(copy_id_):
            copy = original(copy_id_)
            set_committed_value(copy, 'status', CopyStatus.AVAILABLE)  # a pré-checagem enxerga "disponível"
            return copy

        repository.lock_copy = spoofed
        with pytest.raises(CopyUpdateBlockedError) as raised:
            CopyService(repository, db).update_copy(
                copy_id, CopyUpdate(destination=DestinationType.COMMERCIAL, sale_price=9), acervo.seller_id)
        assert raised.value.code == 'copy_not_available'
    assert load(acervo, copy_id).destination == DestinationType.DIDACTIC


def test_service_maps_the_allocation_trigger_to_409_when_the_precheck_is_bypassed(acervo):  # noqa: F811
    with Session(acervo.engine) as db:
        ready_purchase(db, acervo.book_id, acervo.client_id)
        allocated = db.scalar(select(PurchaseReservation.allocated_copy_id).where(
            PurchaseReservation.client_id == acervo.client_id))
    with Session(acervo.engine) as db:
        repository = CopyRepository(db)
        repository.is_allocated_to_reservation = lambda _id: False
        with pytest.raises(CopyUpdateBlockedError) as raised:
            CopyService(repository, db).update_copy(allocated, CopyUpdate(destination=DestinationType.DIDACTIC), acervo.seller_id)
        assert raised.value.code == 'copy_allocated'
    assert load(acervo, allocated).destination == DestinationType.COMMERCIAL


def test_http_reactivation_returns_409_from_the_trigger_when_the_precheck_is_bypassed(acervo, monkeypatch):  # noqa: F811
    deactivate_whole_book(acervo)
    monkeypatch.setattr(BookRepository, 'has_active_copy', lambda self, _id: True)
    response = acervo.http.patch(f'/api/v1/books/{acervo.book_id}', json={'is_active': True})
    assert (response.status_code, response.json()['code']) == (409, 'book_without_active_copy')
    assert book_active(acervo) is False
