"""Consultas de balcão contra PostgreSQL descartável migrado pelo Alembic (ver test_client_requests_postgres)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.controllers.circulation_controller import get_circulation_service
from app.controllers.staff_desk_controller import get_staff_desk_service
from app.dependencies.authentication import get_current_user
from app.main import app
from app.models.domain import (
    Book, Client, Copy, CopyStatus, DestinationType, Employee, Loan, LoanStatus, Profile, PurchaseReservation,
    ReservationStatus, Role, UserRole,
)
from app.models.user import User
from app.repositories.circulation_repository import CirculationRepository
from app.repositories.client_tracking_repository import ClientTrackingRepository
from app.repositories.loan_request_repository import LoanRequestRepository
from app.repositories.staff_desk_repository import StaffDeskRepository
from app.schemas.loan_request_schema import LoanRequestCreate
from app.services.circulation_service import CirculationService
from app.services.client_tracking_service import ClientTrackingService
from app.services.loan_request_service import LoanRequestService, business_today
from app.services.staff_desk_service import StaffDeskService
from test_client_requests_postgres import records  # noqa: F401  (fixture)

BASE = '/api/v1/staff'


def new_user(db, role_code, name):
    role = db.scalar(select(Role).where(Role.code == role_code))
    user = User(name=name, email=f'{uuid4().hex}@test.invalid', password_hash='test')
    db.add(user); db.flush()
    db.add(Profile(id=user.id)); db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    if role_code == 'USER':
        db.add(Client(id=user.id))
    else:
        db.add(Employee(id=user.id, role_id=role.id, employee_code=uuid4().hex))
    db.commit()
    return user.id


@pytest.fixture
def desk(records):  # noqa: F811
    engine, book_id, client_id = records
    with Session(engine) as db:
        seller_id = new_user(db, 'SELLER', 'Balcão Teste')
    sessions = []

    def session():
        db = Session(engine)
        sessions.append(db)
        return db

    app.dependency_overrides[get_staff_desk_service] = lambda: StaffDeskService(db := session(), StaffDeskRepository(db))
    app.dependency_overrides[get_circulation_service] = lambda: CirculationService(db := session(), CirculationRepository(db))
    app.dependency_overrides[get_current_user] = lambda: NS(id=seller_id, role_codes=['SELLER'])
    yield TestClient(app), engine, book_id, client_id, seller_id
    app.dependency_overrides.clear()
    for db in sessions:
        db.close()


def didactic_copy(db, book_id):
    return db.scalar(select(Copy).where(Copy.book_id == book_id, Copy.destination == DestinationType.DIDACTIC))


def commercial_copy(db, book_id):
    return db.scalar(select(Copy).where(Copy.book_id == book_id, Copy.destination == DestinationType.COMMERCIAL))


def test_loan_cycle_from_listing_to_return(desk):
    http, engine, book_id, client_id, seller_id = desk
    with Session(engine) as db:
        LoanRequestService(db, LoanRequestRepository(db)).create(
            LoanRequestCreate(book_id=book_id, pickup_date=business_today()), client_id=client_id)
        didactic_id = didactic_copy(db, book_id).id
    listing = http.get(f'{BASE}/loan-requests', params={'client_id': client_id}).json()
    assert len(listing) == 1
    request = listing[0]
    assert request['client']['id'] == client_id and request['client']['eligible'] is True
    assert request['book']['id'] == book_id
    assert [c['id'] for c in request['eligible_copies']] == [didactic_id]  # exemplar comercial nunca é oferecido
    assert http.get(f'{BASE}/loan-requests', params={'q': 'Livro integração', 'client_id': client_id}).json()[0]['id'] == request['id']
    assert http.get(f'{BASE}/loan-requests', params={'q': 'inexistente-xyz', 'client_id': client_id}).json() == []

    pickup = http.post(f'{BASE}/loan-requests/{request["id"]}/confirm-pickup', json={'copy_id': didactic_id})
    assert pickup.status_code == 200
    assert http.get(f'{BASE}/loan-requests', params={'client_id': client_id}).json() == []
    again = http.post(f'{BASE}/loan-requests/{request["id"]}/confirm-pickup', json={'copy_id': didactic_id})
    assert (again.status_code, again.json()['code']) == (409, 'pickup_already_confirmed')

    loans = http.get(f'{BASE}/loans', params={'client_id': client_id}).json()
    assert len(loans) == 1 and loans[0]['id'] == pickup.json()['id']
    assert (loans[0]['status'], loans[0]['days_late'], loans[0]['copy_id']) == ('ACTIVE', 0, didactic_id)
    assert http.get(f'{BASE}/loans', params={'q': loans[0]['copy_barcode']}).json()[0]['id'] == loans[0]['id']

    assert http.post(f'{BASE}/loans/{loans[0]["id"]}/confirm-return').status_code == 200
    assert http.get(f'{BASE}/loans', params={'client_id': client_id}).json() == []
    closed = http.post(f'{BASE}/loans/{loans[0]["id"]}/confirm-return')
    assert (closed.status_code, closed.json()['code']) == (409, 'loan_already_closed')


def test_overdue_loan_is_listed_with_delay_and_client_becomes_ineligible(desk):
    http, engine, book_id, client_id, seller_id = desk
    with Session(engine) as db:
        copy = didactic_copy(db, book_id)
        now = datetime.now(timezone.utc)
        db.add(Loan(client_id=client_id, copy_id=copy.id, employee_id=seller_id, loan_date=now - timedelta(days=40),
                    due_date=now - timedelta(days=5), status=LoanStatus.OPEN))
        db.commit()
    loan = http.get(f'{BASE}/loans', params={'client_id': client_id}).json()[0]
    assert (loan['status'], loan['days_late'] >= 4) == ('OVERDUE', True)
    assert loan['client']['has_overdue_loan'] is True and loan['client']['eligible'] is False


def test_client_search_matches_name_and_email_and_escapes_wildcards(desk):
    http, engine, _, client_id, seller_id = desk
    with Session(engine) as db:
        needle = uuid4().hex[:12]
        other = new_user(db, 'USER', f'Zé {needle} Silva')
        db.get(User, other).email = f'{needle}@balcao.invalid'
        db.commit()
    by_name = http.get(f'{BASE}/clients', params={'q': f'zé {needle}'}).json()
    assert [c['id'] for c in by_name] == [other]
    assert set(by_name[0]) == {'id', 'name', 'email', 'is_active', 'is_penalized', 'has_overdue_loan', 'eligible'}
    assert [c['id'] for c in http.get(f'{BASE}/clients', params={'q': f'{needle}@BALCAO'}).json()] == [other]
    assert http.get(f'{BASE}/clients', params={'q': '%%'}).json() == []  # curinga é literal
    assert http.get(f'{BASE}/clients', params={'q': needle, 'limit': 1}).json()[0]['id'] == other
    assert seller_id not in [c['id'] for c in http.get(f'{BASE}/clients', params={'q': 'Balcão Teste'}).json()]  # só clientes
    assert http.get(f'{BASE}/clients', params={'q': 'a'}).status_code == 422  # termo curto continua recusado
    assert http.get(f'{BASE}/clients', params={'q': ''}).status_code == 422


def test_client_listing_without_term_lists_only_active_clients_ordered_by_name_with_limit(desk):
    http, engine, _, client_id, seller_id = desk
    tag = uuid4().hex[:8]
    with Session(engine) as db:
        first = new_user(db, 'USER', f'0000 {tag} Alfa')
        second = new_user(db, 'USER', f'0000 {tag} Beta')
        inactive_profile = new_user(db, 'USER', f'0000 {tag} Aaa Perfil')
        inactive_user = new_user(db, 'USER', f'0000 {tag} Aaa Usuario')
        db.get(Profile, inactive_profile).is_active = False
        db.get(User, inactive_user).is_active = False
        db.commit()
    listing = http.get(f'{BASE}/clients', params={'limit': 100})
    assert listing.status_code == 200
    rows = listing.json()
    ids = [c['id'] for c in rows]
    assert inactive_profile not in ids and inactive_user not in ids and seller_id not in ids
    assert all(c['is_active'] for c in rows)
    assert [c['id'] for c in rows if c['name'].startswith(f'0000 {tag}')] == [first, second]
    assert [c['name'] for c in rows] == sorted(c['name'] for c in rows)  # ordenação determinística por nome
    assert len(http.get(f'{BASE}/clients', params={'limit': 1}).json()) == 1
    assert http.get(f'{BASE}/clients', params={'limit': 101}).status_code == 422
    # Com termo, a busca atual continua enxergando clientes inativos (o balcão os mostra como não aptos).
    found = http.get(f'{BASE}/clients', params={'q': f'{tag} Aaa Usuario'}).json()
    assert [(c['id'], c['is_active']) for c in found] == [(inactive_user, False)]


def test_copy_listing_without_term_filters_destination_and_availability_in_order(desk):
    http, engine, book_id, client_id, seller_id = desk
    tag = uuid4().hex[:8]
    title = f'0000 {tag} Listagem'
    with Session(engine) as db:
        db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(seller_id)})
        book = Book(title=title, author='Autor Lista')
        db.add(book); db.flush()
        free_commercial = Copy(book_id=book.id, barcode=f'L172-{tag}-C1', destination=DestinationType.COMMERCIAL, sale_price=9)
        taken_commercial = Copy(book_id=book.id, barcode=f'L172-{tag}-C2', destination=DestinationType.COMMERCIAL,
                                sale_price=9)
        free_didactic = Copy(book_id=book.id, barcode=f'L172-{tag}-D1', destination=DestinationType.DIDACTIC)
        db.add_all([free_commercial, taken_commercial, free_didactic]); db.flush()
        now = datetime.now(timezone.utc)
        db.add(Loan(client_id=client_id, copy_id=taken_commercial.id, employee_id=seller_id, loan_date=now,
                    due_date=now + timedelta(days=30), status=LoanStatus.OPEN))
        db.flush()
        ids = {'c1': free_commercial.id, 'c2': taken_commercial.id, 'd1': free_didactic.id}
        db.commit()

    def listing(**params):
        response = http.get(f'{BASE}/copies', params={'limit': 100, **params})
        assert response.status_code == 200
        return [c for c in response.json() if c['book']['title'] == title]

    assert [c['id'] for c in listing()] == sorted(ids.values())  # título e depois id
    assert [(c['id'], c['sellable']) for c in listing(destination='COMMERCIAL', available='true')] == [(ids['c1'], True)]
    assert [c['id'] for c in listing(destination='DIDACTIC', available='true')] == [ids['d1']]
    assert [c['id'] for c in listing(destination='COMMERCIAL')] == [ids['c1'], ids['c2']]
    assert [c['id'] for c in listing(available='false')] == [ids['c2']]
    all_rows = http.get(f'{BASE}/copies', params={'limit': 100}).json()
    assert [(c['book']['title'], c['id']) for c in all_rows] == sorted((c['book']['title'], c['id']) for c in all_rows)
    assert len(http.get(f'{BASE}/copies', params={'limit': 2}).json()) == 2
    assert http.get(f'{BASE}/copies', params={'limit': 101}).status_code == 422
    assert http.get(f'{BASE}/copies', params={'q': ''}).status_code == 422
    assert http.get(f'{BASE}/copies', params={'q': f'{tag}-D1', 'destination': 'COMMERCIAL'}).json() == []  # q + filtros
    assert [c['id'] for c in http.get(f'{BASE}/copies', params={'q': f'{tag}-D1'}).json()] == [ids['d1']]


def test_inactive_employee_cannot_read_desk(desk):
    http, engine, _, _, seller_id = desk
    with Session(engine) as db:
        db.get(Profile, seller_id).is_active = False
        db.commit()
    for path in ('/clients?q=ana', '/loan-requests', '/loans', '/purchase-reservations'):
        response = http.get(BASE + path)
        assert (response.status_code, response.json()['code']) == (403, 'employee_record_required')


def test_purchase_queue_allocation_and_sale_cycle(desk):
    http, engine, book_id, client_id, seller_id = desk
    with Session(engine) as db:
        copy = commercial_copy(db, book_id)
        copy_id, barcode = copy.id, copy.barcode
        now = datetime.now(timezone.utc)
        loan = Loan(client_id=client_id, copy_id=copy_id, employee_id=seller_id, loan_date=now,
                    due_date=now + timedelta(days=30), status=LoanStatus.OPEN)
        db.add(loan); db.commit()
        loan_id = loan.id
        reservation = ClientTrackingService(db, ClientTrackingRepository(db)).reserve_purchase(client_id, book_id)
        other = new_user(db, 'USER', 'Segundo da fila')
        second = ClientTrackingService(db, ClientTrackingRepository(db)).reserve_purchase(other, book_id)
    items = {i['id']: i for i in http.get(f'{BASE}/purchase-reservations', params={'client_id': client_id}).json()}
    waiting = items[reservation.id]
    assert (waiting['status'], waiting['queue_position'], waiting['free_commercial_copies']) == ('WAITING', 1, 0)
    assert (waiting['can_allocate'], waiting['allocation_blocked_reason']) == (False, 'NO_FREE_COPY')
    blocked = http.post(f'{BASE}/books/{book_id}/allocate-purchase')
    assert (blocked.status_code, blocked.json()['code']) == (409, 'purchase_unavailable')

    assert http.post(f'{BASE}/loans/{loan_id}/confirm-return').status_code == 200
    ready = http.get(f'{BASE}/purchase-reservations', params={'client_id': client_id}).json()[0]
    assert (ready['free_commercial_copies'], ready['can_allocate']) == (1, True)
    behind = http.get(f'{BASE}/purchase-reservations', params={'client_id': other}).json()[0]
    assert (behind['id'], behind['queue_position'], behind['can_allocate'], behind['allocation_blocked_reason']) == (
        second.id, 2, False, 'NOT_FIRST_ELIGIBLE')

    allocated = http.post(f'{BASE}/books/{book_id}/allocate-purchase')
    assert allocated.status_code == 200 and allocated.json()['id'] == reservation.id
    notified = http.get(f'{BASE}/purchase-reservations', params={'client_id': client_id, 'status': 'NOTIFIED'}).json()[0]
    assert (notified['status'], notified['allocated_copy_id'], notified['allocated_copy_barcode']) == ('NOTIFIED', copy_id, barcode)
    assert (notified['queue_position'], notified['free_commercial_copies'], notified['expired']) == (None, 0, False)
    assert http.get(f'{BASE}/purchase-reservations', params={'client_id': client_id, 'status': 'WAITING'}).json() == []
    assert http.get(f'{BASE}/purchase-reservations', params={'q': barcode}).json()[0]['id'] == reservation.id
    # destinação sem exemplar livre: o segundo da fila passa a ser o primeiro, mas sem estoque
    promoted = http.get(f'{BASE}/purchase-reservations', params={'client_id': other}).json()[0]
    assert (promoted['queue_position'], promoted['allocation_blocked_reason']) == (1, 'NO_FREE_COPY')

    assert http.post(f'{BASE}/purchase-reservations/{reservation.id}/confirm-sale').status_code == 200
    assert http.get(f'{BASE}/purchase-reservations', params={'client_id': client_id}).json() == []
    with Session(engine) as db:
        assert db.get(Copy, copy_id).status == CopyStatus.SOLD


def test_ineligible_first_in_queue_is_skipped_keeping_position(desk):
    http, engine, book_id, client_id, seller_id = desk
    with Session(engine) as db:
        copy_id = commercial_copy(db, book_id).id
        now = datetime.now(timezone.utc)
        loan = Loan(client_id=client_id, copy_id=copy_id, employee_id=seller_id, loan_date=now,
                    due_date=now + timedelta(days=30), status=LoanStatus.OPEN)
        db.add(loan); db.commit()
        tracking = ClientTrackingService(db, ClientTrackingRepository(db))
        first = tracking.reserve_purchase(client_id, book_id)
        other = new_user(db, 'USER', 'Elegível atrás')
        tracking.reserve_purchase(other, book_id)
        CirculationService(db, CirculationRepository(db)).confirm_return(loan.id, seller_id)
        db.get(Client, client_id).is_penalized = True
        db.commit()
    head = http.get(f'{BASE}/purchase-reservations', params={'client_id': client_id}).json()[0]
    assert (head['id'], head['client']['eligible'], head['can_allocate'], head['allocation_blocked_reason']) == (
        first.id, False, False, 'CLIENT_INELIGIBLE')
    response = http.post(f'{BASE}/books/{book_id}/allocate-purchase')
    assert response.status_code == 200
    behind = http.get(f'{BASE}/purchase-reservations', params={'client_id': other, 'status': 'NOTIFIED'}).json()[0]
    assert (behind['status'], behind['allocated_copy_id'], behind['expired']) == ('NOTIFIED', copy_id, False)
    skipped = http.get(f'{BASE}/purchase-reservations', params={'client_id': client_id}).json()[0]
    assert (skipped['id'], skipped['status'], skipped['queue_position']) == (first.id, 'WAITING', 1)


def test_borrowed_didactic_copy_is_not_offered_for_pickup(desk):
    http, engine, book_id, client_id, seller_id = desk
    with Session(engine) as db:
        LoanRequestService(db, LoanRequestRepository(db)).create(
            LoanRequestCreate(book_id=book_id, pickup_date=business_today()), client_id=client_id)
        borrower = new_user(db, 'USER', 'Outro tomador')
        now = datetime.now(timezone.utc)
        db.add(Loan(client_id=borrower, copy_id=didactic_copy(db, book_id).id, employee_id=seller_id, loan_date=now,
                    due_date=now + timedelta(days=30), status=LoanStatus.OPEN))
        db.commit()
    request = http.get(f'{BASE}/loan-requests', params={'client_id': client_id}).json()[0]
    assert request['eligible_copies'] == []


def test_pendencies_use_v2_cutoff_and_do_not_write(desk):
    http, engine, book_id, client_id, seller_id = desk
    from datetime import time
    from app.core.business_dates import BUSINESS_ZONE
    with Session(engine) as db:
        copy = didactic_copy(db, book_id)
        now = datetime.now(BUSINESS_ZONE)
        # vence hoje, em horário já passado: V1 contaria atraso, V2 não
        due = datetime.combine(now.date(), time(0, 1), BUSINESS_ZONE)
        db.add(Loan(client_id=client_id, copy_id=copy.id, employee_id=seller_id, loan_date=due - timedelta(days=30),
                    due_date=due, status=LoanStatus.OPEN))
        db.commit()
    body = http.get(f'{BASE}/clients/{client_id}/pendencies').json()
    assert body['client']['id'] == client_id and body['client']['eligible'] is True
    assert body['overdue_loans'] == []
    with Session(engine) as db:
        late = datetime.now(BUSINESS_ZONE) - timedelta(days=3)
        db.add(Loan(client_id=client_id, copy_id=commercial_copy(db, book_id).id, employee_id=seller_id,
                    loan_date=late - timedelta(days=30), due_date=late, status=LoanStatus.OPEN))
        db.commit()
    body = http.get(f'{BASE}/clients/{client_id}/pendencies').json()
    assert [l['status'] for l in body['overdue_loans']] == ['OVERDUE']
    assert body['client']['has_overdue_loan'] is True and body['client']['eligible'] is False
    assert body['client']['is_penalized'] is False  # consulta não sincroniza penalidade
    with Session(engine) as db:
        assert db.get(Client, client_id).is_penalized is False


def test_pendencies_unknown_client_is_404_and_inactive_employee_403(desk):
    http, engine, _, _, seller_id = desk
    response = http.get(f'{BASE}/clients/2147483646/pendencies')
    assert (response.status_code, response.json()['code']) == (404, 'client_not_found')
    with Session(engine) as db:
        db.get(Profile, seller_id).is_active = False
        db.commit()
    assert http.get(f'{BASE}/clients/1/pendencies').status_code == 403


def test_dashboard_requires_active_employee_and_never_writes(desk):
    http, engine, _, _, seller_id = desk
    assert set(http.get(f'{BASE}/dashboard').json()) == {'active_loans', 'returns_today', 'waiting_reservations', 'pendencies'}
    with Session(engine) as db:
        db.get(Profile, seller_id).is_active = False
        db.commit()
    response = http.get(f'{BASE}/dashboard')
    assert (response.status_code, response.json()['code']) == (403, 'employee_record_required')


def test_dashboard_indicator_definitions_and_sao_paulo_day_edges(desk):
    from datetime import time
    from app.core.business_dates import BUSINESS_ZONE, business_today as today_sp
    http, engine, book_id, client_id, seller_id = desk
    before = http.get(f'{BASE}/dashboard').json()
    midnight = datetime.combine(today_sp(), time.min, BUSINESS_ZONE)
    now = datetime.now(BUSINESS_ZONE)
    with Session(engine) as db:
        def new_copy(destination=DestinationType.DIDACTIC):
            db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(seller_id)})
            copy = Copy(book_id=book_id, barcode=uuid4().hex, destination=destination,
                        sale_price=25 if destination == DestinationType.COMMERCIAL else None)
            db.add(copy); db.flush()
            return copy.id

        def returned(returned_at):
            loan = Loan(client_id=client_id, copy_id=new_copy(), employee_id=seller_id,
                        loan_date=returned_at - timedelta(days=10), due_date=returned_at + timedelta(days=1),
                        status=LoanStatus.OPEN)
            db.add(loan); db.flush()
            loan.status, loan.returned_at = LoanStatus.RETURNED, returned_at  # a trigger exige início OPEN
            db.flush()
        returned(midnight)                                   # 00:00 de hoje em São Paulo: conta
        returned(midnight + timedelta(days=1) - timedelta(seconds=1))  # 23:59:59 de hoje: conta
        returned(midnight - timedelta(seconds=1))            # 23:59:59 de ontem: não conta
        returned(midnight + timedelta(days=1))               # 00:00 de amanhã: não conta
        # empréstimos OPEN: um em atraso (cliente A), outro em dia
        late_client = new_user(db, 'USER', 'Atrasado dois empréstimos')
        for due in (midnight - timedelta(seconds=1), midnight - timedelta(days=3)):
            db.add(Loan(client_id=late_client, copy_id=new_copy(), employee_id=seller_id, loan_date=due - timedelta(days=30),
                        due_date=due, status=LoanStatus.OPEN))
        # vence hoje (00:01): ativo, não é atraso pela regra V2
        db.add(Loan(client_id=client_id, copy_id=new_copy(), employee_id=seller_id, loan_date=midnight - timedelta(days=30),
                    due_date=midnight + timedelta(minutes=1), status=LoanStatus.OPEN))
        db.commit()
        waiting_client = new_user(db, 'USER', 'Fila do painel')
        db.add(Loan(client_id=client_id, copy_id=commercial_copy(db, book_id).id, employee_id=seller_id,
                    loan_date=midnight, due_date=midnight + timedelta(days=30), status=LoanStatus.OPEN))
        db.flush()  # reserva só é aceita se o exemplar comercial está emprestado
        db.add(PurchaseReservation(client_id=waiting_client, book_id=book_id, status=ReservationStatus.WAITING, queue_position=1))
        db.commit()
    after = http.get(f'{BASE}/dashboard').json()
    assert after['returns_today'] - before['returns_today'] == 2
    assert after['active_loans'] - before['active_loans'] == 4
    assert after['pendencies'] - before['pendencies'] == 1  # cliente distinto, apesar de 2 empréstimos atrasados
    assert after['waiting_reservations'] - before['waiting_reservations'] == 1
