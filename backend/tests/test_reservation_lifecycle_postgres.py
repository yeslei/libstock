"""Prazo de retirada, expiração, cancelamento e primeiro elegível das reservas de compra (Issue #150)
contra PostgreSQL descartável migrado pelo Alembic (ver test_client_requests_postgres)."""
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.business_dates import BUSINESS_ZONE, business_today, reservation_pickup_deadline
from app.core.exceptions import ApplicationError
from app.controllers.client_tracking_controller import get_client_tracking_service
from app.dependencies.authentication import get_current_user
from app.models.domain import (
    AuditLog, Book, Client, Copy, CopyStatus, Loan, LoanStatus, PurchaseReservation, ReservationStatus, SaleItem,
)
from app.repositories.circulation_repository import CirculationRepository
from app.repositories.client_tracking_repository import ClientTrackingRepository
from app.services.circulation_service import CirculationService
from app.services.client_tracking_service import ClientTrackingService
from test_client_requests_postgres import records  # noqa: F401  (fixture)
from test_staff_desk_postgres import BASE, commercial_copy, desk, new_user  # noqa: F401  (fixtures/helpers)
from app.main import app

MINE = '/api/v1/purchase-reservations'


def as_user(engine, user_id, role):
    app.dependency_overrides[get_client_tracking_service] = lambda: ClientTrackingService(db := Session(engine), ClientTrackingRepository(db))
    app.dependency_overrides[get_current_user] = lambda: NS(id=user_id, role_codes=[role])


def circulation(db):
    return CirculationService(db, CirculationRepository(db))


def waiting_queue(engine, book_id, client_id, seller_id, extra_clients=0):
    """Fila WAITING sobre exemplar comercial livre: o exemplar emprestado é devolvido depois das reservas."""
    with Session(engine) as db:
        copy = commercial_copy(db, book_id)
        now = datetime.now(timezone.utc)
        loan = Loan(client_id=client_id, copy_id=copy.id, employee_id=seller_id, loan_date=now,
                    due_date=now + timedelta(days=30), status=LoanStatus.OPEN)
        db.add(loan); db.commit()
        tracking = ClientTrackingService(db, ClientTrackingRepository(db))
        clients = [client_id] + [new_user(db, 'USER', f'Fila {n}') for n in range(extra_clients)]
        reservations = [tracking.reserve_purchase(c, book_id).id for c in clients]
        circulation(db).confirm_return(loan.id, seller_id)
        return clients, reservations, copy.id


def state(engine, reservation_id):
    with Session(engine) as db:
        row = db.get(PurchaseReservation, reservation_id)
        db.refresh(row)
        return row.status.value, row.allocated_copy_id, row.expires_at


def force_expired(engine, reservation_id):
    with Session(engine) as db:
        db.execute(text("UPDATE purchase_reservations SET requested_at = now() - interval '10 days', "
                        "expires_at = now() - interval '1 minute' WHERE id = :id"), {'id': reservation_id})
        db.commit()


def audit(engine, reservation_id, operation):
    with Session(engine) as db:
        return db.scalars(select(AuditLog).where(
            AuditLog.entity_type == 'purchase_reservations', AuditLog.entity_id == str(reservation_id),
            AuditLog.operation == operation).order_by(AuditLog.id)).all()


# ---- prazo -----------------------------------------------------------------

@pytest.mark.parametrize('allocated_at,expected', [
    (datetime(2026, 10, 3, 12, 0, tzinfo=BUSINESS_ZONE), datetime(2026, 10, 8, 23, 59, 59, 999000, tzinfo=BUSINESS_ZONE)),
    # 23:30 em São Paulo (02:30 UTC do dia seguinte) ainda é 03/10 no negócio
    (datetime(2026, 10, 4, 2, 30, tzinfo=timezone.utc), datetime(2026, 10, 8, 23, 59, 59, 999000, tzinfo=BUSINESS_ZONE)),
    # 00:30 em São Paulo já é 04/10
    (datetime(2026, 10, 4, 3, 30, tzinfo=timezone.utc), datetime(2026, 10, 9, 23, 59, 59, 999000, tzinfo=BUSINESS_ZONE)),
    # virada de mês e de ano
    (datetime(2026, 12, 29, 10, 0, tzinfo=BUSINESS_ZONE), datetime(2027, 1, 3, 23, 59, 59, 999000, tzinfo=BUSINESS_ZONE)),
])
def test_pickup_deadline_is_end_of_fifth_calendar_day_in_sao_paulo(allocated_at, expected):
    assert reservation_pickup_deadline(allocated_at) == expected


def test_allocation_persists_deadline(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    clients, (reservation_id,), _ = waiting_queue(engine, book_id, client_id, seller_id)
    assert state(engine, reservation_id)[2] is None  # sem destinação, sem prazo
    assert http.post(f'{BASE}/books/{book_id}/allocate-purchase').status_code == 200
    status, _, expires_at = state(engine, reservation_id)
    local = expires_at.astimezone(BUSINESS_ZONE)
    assert status == 'NOTIFIED'
    assert (local.date(), local.hour, local.minute, local.second, local.microsecond) == (
        business_today() + timedelta(days=5), 23, 59, 59, 999000)
    tracking = ClientTrackingService(Session(engine), ClientTrackingRepository(Session(engine))).reservations(client_id)[0]
    assert (tracking.expires_at, tracking.expired) == (expires_at, False)


# ---- expiração --------------------------------------------------------------

def test_expired_reservation_releases_copy_for_next_allocation(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    clients, (first, second), copy_id = waiting_queue(engine, book_id, client_id, seller_id, extra_clients=1)
    assert http.post(f'{BASE}/books/{book_id}/allocate-purchase').json()['id'] == first
    force_expired(engine, first)
    # a consulta apenas sinaliza: nada é gravado
    listed = http.get(f'{BASE}/purchase-reservations', params={'client_id': client_id}).json()[0]
    assert (listed['status'], listed['expired']) == ('NOTIFIED', True)
    assert state(engine, first)[0] == 'NOTIFIED'
    as_user(engine, client_id, 'USER')
    mine = http.get(f'{MINE}/me').json()[0]
    assert (mine['status'], mine['expired']) == ('NOTIFIED', True)
    assert state(engine, first)[0] == 'NOTIFIED'
    as_user(engine, seller_id, 'SELLER')
    # a destinação seguinte efetiva a expiração e reaproveita o exemplar liberado
    assert http.post(f'{BASE}/books/{book_id}/allocate-purchase').json()['id'] == second
    assert state(engine, first)[0] == 'EXPIRED'
    assert state(engine, second)[:2] == ('NOTIFIED', copy_id)
    assert len(audit(engine, first, 'UPDATE')) >= 1


def test_confirm_sale_after_deadline_is_refused_and_persists_expiration(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    clients, (reservation_id,), copy_id = waiting_queue(engine, book_id, client_id, seller_id)
    http.post(f'{BASE}/books/{book_id}/allocate-purchase')
    force_expired(engine, reservation_id)
    response = http.post(f'{BASE}/purchase-reservations/{reservation_id}/confirm-sale')
    assert (response.status_code, response.json()['code']) == (409, 'reservation_expired')
    assert state(engine, reservation_id)[0] == 'EXPIRED'  # efetivada apesar do erro
    with Session(engine) as db:
        assert db.scalar(select(SaleItem.id).where(SaleItem.copy_id == copy_id)) is None
        assert db.get(Copy, copy_id).status == CopyStatus.AVAILABLE
    again = http.post(f'{BASE}/purchase-reservations/{reservation_id}/confirm-sale')
    assert (again.status_code, again.json()['code']) == (409, 'reservation_not_ready')
    # o exemplar foi liberado: a reserva vencida não impede o cliente de reservar de novo (duplicidade) e
    # o exemplar volta a ser livre para venda/compra, não mais retido
    with Session(engine) as db:
        tracking = ClientTrackingService(db, ClientTrackingRepository(db))
        with pytest.raises(ApplicationError) as error:
            tracking.reserve_purchase(client_id, book_id)
        assert error.value.code == 'reservation_unavailable'  # sem exemplar a aguardar: é caso de compra direta
        assert CirculationRepository(db).lock_free_copy(book_id, commercial_copy(db, book_id).destination) is not None


def test_explicit_expiration_endpoint_releases_overdue_reservations(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    clients, (reservation_id,), _ = waiting_queue(engine, book_id, client_id, seller_id)
    http.post(f'{BASE}/books/{book_id}/allocate-purchase')
    as_user(engine, client_id, 'USER')
    assert http.post(f'{BASE}/purchase-reservations/expire').status_code == 403
    as_user(engine, seller_id, 'SELLER')
    http.post(f'{BASE}/purchase-reservations/expire')  # a base é compartilhada: zera vencidas de outros testes
    assert http.post(f'{BASE}/purchase-reservations/expire').json() == {'expired': 0}
    force_expired(engine, reservation_id)
    assert http.post(f'{BASE}/purchase-reservations/expire').json() == {'expired': 1}
    assert state(engine, reservation_id)[0] == 'EXPIRED'
    assert http.post(f'{BASE}/purchase-reservations/expire').json() == {'expired': 0}
    app.dependency_overrides.pop(get_current_user)
    assert http.post(f'{BASE}/purchase-reservations/expire').status_code == 401


# ---- cancelamento -----------------------------------------------------------

def test_client_cancels_own_waiting_and_notified_reservations(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    clients, (first, second), copy_id = waiting_queue(engine, book_id, client_id, seller_id, extra_clients=1)
    http.post(f'{BASE}/books/{book_id}/allocate-purchase')
    as_user(engine, clients[1], 'USER')
    waiting = http.post(f'{MINE}/{second}/cancel')
    assert (waiting.status_code, waiting.json()) == (200, {'id': second})
    assert state(engine, second)[0] == 'CANCELLED'
    as_user(engine, client_id, 'USER')
    notified = http.post(f'{MINE}/{first}/cancel')
    assert (notified.status_code, notified.json()) == (200, {'id': first})
    assert state(engine, first)[0] == 'CANCELLED'
    with Session(engine) as db:
        assert db.get(Copy, copy_id).status == CopyStatus.AVAILABLE
        assert CirculationRepository(db).lock_free_copy(book_id, commercial_copy(db, book_id).destination) is not None
    entry = audit(engine, first, 'CANCEL')[0]
    assert (entry.employee_id, entry.new_value['actor_user_id'], entry.new_value['actor_role']) == (None, client_id, 'USER')
    assert any(row.new_value['status'] == 'CANCELLED' for row in audit(engine, first, 'UPDATE'))


def test_client_cannot_cancel_someone_elses_reservation(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    clients, (first, second), _ = waiting_queue(engine, book_id, client_id, seller_id, extra_clients=1)
    as_user(engine, clients[1], 'USER')
    response = http.post(f'{MINE}/{first}/cancel')
    assert (response.status_code, response.json()['code']) == (404, 'reservation_not_found')
    assert state(engine, first)[0] == 'WAITING'
    assert http.post(f'{MINE}/999999999/cancel').json()['code'] == 'reservation_not_found'
    as_user(engine, seller_id, 'SELLER')
    assert http.post(f'{MINE}/{first}/cancel').status_code == 403  # rota do cliente: só USER
    app.dependency_overrides.pop(get_current_user)
    assert http.post(f'{MINE}/{first}/cancel').status_code == 401
    assert http.post(f'{MINE}/0/cancel').status_code in (401, 422)


def test_staff_cancels_any_reservation_with_reason_and_audit(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    clients, (first, second), copy_id = waiting_queue(engine, book_id, client_id, seller_id, extra_clients=1)
    http.post(f'{BASE}/books/{book_id}/allocate-purchase')
    response = http.post(f'{BASE}/purchase-reservations/{first}/cancel', json={'reason': 'Cliente desistiu no balcão'})
    assert (response.status_code, response.json()) == (200, {'id': first})
    assert state(engine, first)[0] == 'CANCELLED'
    entry = audit(engine, first, 'CANCEL')[0]
    assert (entry.employee_id, entry.new_value) == (seller_id, {
        'actor_user_id': seller_id, 'actor_role': 'STAFF', 'reason': 'Cliente desistiu no balcão'})
    # sem corpo: motivo opcional
    assert http.post(f'{BASE}/purchase-reservations/{second}/cancel').status_code == 200
    assert audit(engine, second, 'CANCEL')[0].new_value['reason'] is None
    assert http.post(f'{BASE}/purchase-reservations/{first}/cancel', json={'reason': 'x' * 256}).status_code == 422
    assert http.post(f'{BASE}/purchase-reservations/{first}/cancel', json={'outro': 1}).status_code == 422
    assert http.post(f'{BASE}/purchase-reservations/999999999/cancel').json()['code'] == 'reservation_not_found'
    as_user(engine, client_id, 'USER')
    assert http.post(f'{BASE}/purchase-reservations/{first}/cancel').status_code == 403


def test_final_states_are_not_cancellable(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    clients, (cancelled, fulfilled, expired), _ = waiting_queue(engine, book_id, client_id, seller_id, extra_clients=2)
    assert http.post(f'{BASE}/purchase-reservations/{cancelled}/cancel').status_code == 200
    http.post(f'{BASE}/books/{book_id}/allocate-purchase')  # segunda da fila
    assert http.post(f'{BASE}/purchase-reservations/{fulfilled}/confirm-sale').status_code == 200
    http.post(f'{BASE}/books/{book_id}/allocate-purchase')  # sem exemplar livre: a terceira segue aguardando
    with Session(engine) as db:
        db.execute(text("UPDATE purchase_reservations SET status='EXPIRED' WHERE id=:id"), {'id': expired})
        db.commit()
    for reservation_id, status in ((cancelled, 'CANCELLED'), (fulfilled, 'FULFILLED'), (expired, 'EXPIRED')):
        for owner_role in ('staff', 'client'):
            if owner_role == 'staff':
                as_user(engine, seller_id, 'SELLER')
                response = http.post(f'{BASE}/purchase-reservations/{reservation_id}/cancel')
            else:
                as_user(engine, clients[[cancelled, fulfilled, expired].index(reservation_id)], 'USER')
                response = http.post(f'{MINE}/{reservation_id}/cancel')
            body = response.json()
            assert (response.status_code, body['code'], body['details']) == (
                409, 'reservation_not_cancellable', {'status': status})
        assert state(engine, reservation_id)[0] == status


def test_cancelling_an_overdue_notified_reservation_persists_expiration_and_refuses(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    clients, (reservation_id,), copy_id = waiting_queue(engine, book_id, client_id, seller_id)
    http.post(f'{BASE}/books/{book_id}/allocate-purchase')
    force_expired(engine, reservation_id)
    response = http.post(f'{BASE}/purchase-reservations/{reservation_id}/cancel')
    assert (response.status_code, response.json()['code'], response.json()['details']) == (
        409, 'reservation_not_cancellable', {'status': 'EXPIRED'})
    assert state(engine, reservation_id)[0] == 'EXPIRED'


# ---- primeiro elegível ------------------------------------------------------

def test_allocation_goes_to_first_eligible_and_ineligible_keep_position(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    clients, (first, second, third), copy_id = waiting_queue(engine, book_id, client_id, seller_id, extra_clients=2)
    with Session(engine) as db:
        db.get(Client, clients[0]).is_penalized = True
        db.commit()
    listed = {}
    for client in clients:
        item = http.get(f'{BASE}/purchase-reservations', params={'client_id': client}).json()[0]
        listed[item['id']] = item
    assert [(listed[i]['queue_position'], listed[i]['can_allocate'], listed[i]['allocation_blocked_reason'])
            for i in (first, second, third)] == [
        (1, False, 'CLIENT_INELIGIBLE'), (2, True, None), (3, False, 'NOT_FIRST_ELIGIBLE')]
    assert http.post(f'{BASE}/books/{book_id}/allocate-purchase').json()['id'] == second
    assert state(engine, first)[0] == 'WAITING' and state(engine, third)[0] == 'WAITING'
    assert state(engine, second)[:2] == ('NOTIFIED', copy_id)
    # posição preservada para o inelegível quando ele volta a ser elegível
    with Session(engine) as db:
        db.get(Client, clients[0]).is_penalized = False
        db.commit()
    again = http.get(f'{BASE}/purchase-reservations', params={'client_id': clients[0]}).json()[0]
    assert (again['queue_position'], again['allocation_blocked_reason']) == (1, 'NO_FREE_COPY')


def test_no_eligible_reservation_is_a_stable_conflict_and_changes_nothing(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    clients, (first, second), copy_id = waiting_queue(engine, book_id, client_id, seller_id, extra_clients=1)
    with Session(engine) as db:
        for client in clients:
            db.get(Client, client).is_penalized = True
        db.commit()
    response = http.post(f'{BASE}/books/{book_id}/allocate-purchase')
    assert (response.status_code, response.json()['code']) == (409, 'no_eligible_reservation')
    assert state(engine, first)[0] == 'WAITING' and state(engine, second)[0] == 'WAITING'
    with Session(engine) as db:
        assert CirculationRepository(db).lock_free_copy(book_id, commercial_copy(db, book_id).destination) is not None


# ---- concorrência (ordem forçada pelo lock do livro) -------------------------

def blocked_count(engine):
    with engine.connect() as conn:
        return conn.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                                 "AND wait_event_type = 'Lock'")).scalar()


def wait_blocked(engine, expected, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if blocked_count(engine) >= expected:
            return
        time.sleep(0.05)
    raise AssertionError('a operação concorrente não ficou esperando pelo lock do livro')


def outcome(call):
    try:
        call()
        return 'ok'
    except ApplicationError as error:
        return error.code


def run_in_order(engine, book_id, seller_id, first_op, second_op):
    """Segura o lock do livro, enfileira first_op e depois second_op (fila FIFO do PostgreSQL) e libera."""
    holder = Session(engine)
    holder.execute(select(Book).where(Book.id == book_id).with_for_update())

    def run(operation):
        with Session(engine) as db:
            return outcome(lambda: operation(circulation(db)))
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, first_op)
        wait_blocked(engine, 1)
        second = pool.submit(run, second_op)
        try:
            wait_blocked(engine, 2)
        finally:
            holder.commit()
            holder.close()
        return first.result(timeout=30), second.result(timeout=30)


@pytest.mark.parametrize('cancel_first,expected_outcomes,final', [
    (False, ('ok', 'ok'), 'CANCELLED'),  # destina e depois cancela: exemplar volta a ficar livre
    (True, ('ok', 'reservation_not_found'), 'CANCELLED'),  # cancela antes: não há mais reserva aguardando
])
def test_allocation_versus_cancellation_is_serialized(desk, cancel_first, expected_outcomes, final):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    clients, (reservation_id,), copy_id = waiting_queue(engine, book_id, client_id, seller_id)
    allocate = lambda s: s.allocate_purchase(book_id, seller_id)  # noqa: E731
    cancel = lambda s: s.cancel_reservation_by_staff(reservation_id, seller_id)  # noqa: E731
    ops = (cancel, allocate) if cancel_first else (allocate, cancel)
    results = run_in_order(engine, book_id, seller_id, *ops)
    assert results == expected_outcomes
    assert state(engine, reservation_id)[0] == final
    with Session(engine) as db:
        assert CirculationRepository(db).lock_free_copy(book_id, commercial_copy(db, book_id).destination) is not None


@pytest.mark.parametrize('cancel_first,expected_outcomes,final', [
    (False, ('ok', 'reservation_not_cancellable'), 'FULFILLED'),  # vende primeiro: cancelar é recusado
    (True, ('ok', 'reservation_not_ready'), 'CANCELLED'),  # cancela primeiro: venda recusada
])
def test_confirm_sale_versus_cancellation_is_serialized(desk, cancel_first, expected_outcomes, final):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    clients, (reservation_id,), copy_id = waiting_queue(engine, book_id, client_id, seller_id)
    http.post(f'{BASE}/books/{book_id}/allocate-purchase')
    sell = lambda s: s.confirm_sale(reservation_id, seller_id)  # noqa: E731
    cancel = lambda s: s.cancel_reservation_by_staff(reservation_id, seller_id)  # noqa: E731
    ops = (cancel, sell) if cancel_first else (sell, cancel)
    results = run_in_order(engine, book_id, seller_id, *ops)
    assert results == expected_outcomes
    assert state(engine, reservation_id)[0] == final
    with Session(engine) as db:
        sold = db.scalar(select(SaleItem.id).where(SaleItem.copy_id == copy_id)) is not None
        assert sold == (final == 'FULFILLED')
        assert db.get(Copy, copy_id).status == (CopyStatus.SOLD if sold else CopyStatus.AVAILABLE)


def test_rollback_keeps_reservation_when_cancel_audit_fails(desk, monkeypatch):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    clients, (reservation_id,), _ = waiting_queue(engine, book_id, client_id, seller_id)

    def boom(*args, **kwargs):
        from sqlalchemy.exc import SQLAlchemyError
        raise SQLAlchemyError('falha simulada')
    monkeypatch.setattr(CirculationRepository, 'record_cancellation', boom)
    response = http.post(f'{BASE}/purchase-reservations/{reservation_id}/cancel')
    assert (response.status_code, response.json()['code']) == (500, 'circulation_persistence_error')
    assert state(engine, reservation_id)[0] == 'WAITING'


def test_purchase_request_with_free_copy_is_an_allocation_with_the_same_deadline_and_expires(desk):  # noqa: F811
    from app.repositories.purchase_request_repository import PurchaseRequestRepository
    from app.schemas.purchase_request_schema import PurchaseRequestCreate
    from app.services.purchase_request_service import PurchaseRequestService
    http, engine, book_id, client_id, seller_id = desk
    with Session(engine) as db:
        PurchaseRequestService(db, PurchaseRequestRepository(db)).create(
            PurchaseRequestCreate(book_id=book_id, pickup_date=business_today()), client_id=client_id)
        reservation = db.scalar(select(PurchaseReservation).where(
            PurchaseReservation.client_id == client_id, PurchaseReservation.book_id == book_id,
            PurchaseReservation.status == ReservationStatus.NOTIFIED))
        reservation_id, copy_id = reservation.id, reservation.allocated_copy_id
        assert reservation.expires_at == reservation_pickup_deadline(reservation.notified_at)
        local = reservation.expires_at.astimezone(BUSINESS_ZONE)
        assert (local.date(), local.hour, local.minute, local.microsecond) == (
            business_today() + timedelta(days=5), 23, 59, 999000)
    force_expired(engine, reservation_id)
    # expira pelas mesmas regras: a venda é recusada e o exemplar é liberado
    response = http.post(f'{BASE}/purchase-reservations/{reservation_id}/confirm-sale')
    assert (response.status_code, response.json()['code']) == (409, 'reservation_expired')
    assert state(engine, reservation_id)[0] == 'EXPIRED'
    with Session(engine) as db:
        assert db.get(Copy, copy_id).status == CopyStatus.AVAILABLE
        assert CirculationRepository(db).lock_free_copy(book_id, commercial_copy(db, book_id).destination) is not None
