"""Comprovantes (Issue #152) contra PostgreSQL descartável migrado pelo Alembic."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.controllers.receipt_controller import get_receipt_service
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_sale_service
from app.main import app
from app.models.domain import Loan, LoanStatus, Profile, Sale, SaleItem, SaleStatus
from app.repositories.loan_request_repository import LoanRequestRepository
from app.repositories.receipt_repository import ReceiptRepository
from app.schemas.loan_request_schema import LoanRequestCreate
from app.services.loan_request_service import LoanRequestService, business_today
from app.services.receipt_service import ReceiptService
from test_client_requests_postgres import records  # noqa: F401  (fixture)
from test_direct_sale_postgres import new_commercial, sale_service
from test_staff_desk_postgres import BASE, desk, didactic_copy, new_user  # noqa: F401  (fixtures)

RECEIPTS = '/api/v1/receipts'
SAO_PAULO = ZoneInfo('America/Sao_Paulo')


@pytest.fixture
def receipts(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    sessions = []

    def service():
        db = Session(engine)
        sessions.append(db)
        return ReceiptService(db, ReceiptRepository(db))

    app.dependency_overrides[get_receipt_service] = service
    yield http, engine, book_id, client_id, seller_id
    for db in sessions:
        db.close()


def request_pickup(http, engine, book_id, client_id):
    """Solicita e confirma a retirada pelo balcão; devolve (loan_id, copy_id)."""
    with Session(engine) as db:
        request = LoanRequestService(db, LoanRequestRepository(db)).create(
            LoanRequestCreate(book_id=book_id, pickup_date=business_today()), client_id=client_id)
        copy_id = didactic_copy(db, book_id).id
    response = http.post(f'{BASE}/loan-requests/{request.id}/confirm-pickup', json={'copy_id': copy_id})
    assert response.status_code == 200
    return response.json()['id'], copy_id


def closed_loan(db, client_id, copy_id, employee_id, status, loan_date, due_date, returned_at):
    """O gatilho exige que todo empréstimo nasça OPEN; o encerramento vem em seguida."""
    db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(employee_id)})
    loan = Loan(client_id=client_id, copy_id=copy_id, employee_id=employee_id, status=LoanStatus.OPEN,
                loan_date=loan_date, due_date=due_date)
    db.add(loan)
    db.flush()
    loan.status, loan.returned_at = status, returned_at
    db.flush()
    return loan.id


def as_user(user_id, role):
    app.dependency_overrides[get_current_user] = lambda: NS(id=user_id, role_codes=[role])


def counts(engine):
    with Session(engine) as db:
        return (db.scalar(select(func.count()).select_from(Loan)),
                db.scalar(select(func.count()).select_from(Sale)),
                db.scalar(text('SELECT count(*) FROM audit_logs')))


def test_pickup_loan_receipt_and_return_receipt_use_persisted_data(receipts):
    http, engine, book_id, client_id, seller_id = receipts
    loan_id, copy_id = request_pickup(http, engine, book_id, client_id)
    receipt = http.get(f'{RECEIPTS}/loans/{loan_id}')
    assert receipt.status_code == 200
    body = receipt.json()
    with Session(engine) as db:
        loan = db.get(Loan, loan_id)
        barcode = didactic_copy(db, book_id).barcode
        assert body['number'] == loan_id and body['copy_id'] == copy_id and body['copy_barcode'] == barcode
        assert datetime.fromisoformat(body['loan_date']) == loan.loan_date
        assert datetime.fromisoformat(body['due_date']) == loan.due_date
    assert body['client'] == {'id': client_id, 'name': 'Teste Cliente', 'code': None}
    assert body['employee']['id'] == seller_id and body['employee']['name'] == 'Balcão Teste'
    assert body['book'] == {'title': 'Livro integração', 'author': 'Autor', 'isbn': None}
    assert http.get(f'{RECEIPTS}/loans/{loan_id}').json() == body  # reimpressão idêntica

    assert http.get(f'{RECEIPTS}/returns/{loan_id}').status_code == 409
    assert http.get(f'{RECEIPTS}/returns/{loan_id}').json()['code'] == 'loan_not_returned'
    assert http.post(f'{BASE}/loans/{loan_id}/confirm-return').status_code == 200
    returned = http.get(f'{RECEIPTS}/returns/{loan_id}')
    assert returned.status_code == 200
    data = returned.json()
    with Session(engine) as db:
        assert datetime.fromisoformat(data['returned_at']) == db.get(Loan, loan_id).returned_at
    assert data['days_late'] == 0 and data['number'] == loan_id and data['book'] == body['book']
    # o comprovante de empréstimo continua disponível depois da devolução
    assert http.get(f'{RECEIPTS}/loans/{loan_id}').json() == body


def test_return_receipt_counts_late_days_by_business_calendar(receipts):
    http, engine, book_id, client_id, seller_id = receipts
    with Session(engine) as db:
        copy_id = didactic_copy(db, book_id).id
        late_id = closed_loan(db, client_id, copy_id, seller_id, LoanStatus.RETURNED,
                              datetime(2026, 1, 1, 10, tzinfo=SAO_PAULO), datetime(2026, 1, 10, 23, 30, tzinfo=SAO_PAULO),
                              datetime(2026, 1, 13, 0, 10, tzinfo=SAO_PAULO))
        on_time_id = closed_loan(db, client_id, copy_id, seller_id, LoanStatus.RETURNED,
                                 datetime(2026, 2, 1, 10, tzinfo=SAO_PAULO), datetime(2026, 2, 10, 8, tzinfo=SAO_PAULO),
                                 datetime(2026, 2, 10, 20, tzinfo=SAO_PAULO))
        db.commit()
    assert http.get(f'{RECEIPTS}/returns/{late_id}').json()['days_late'] == 3
    assert http.get(f'{RECEIPTS}/returns/{on_time_id}').json()['days_late'] == 0  # vencer hoje não é atraso


def test_missing_cancelled_and_invalid_ids(receipts):
    http, engine, book_id, client_id, seller_id = receipts
    with Session(engine) as db:
        now = datetime.now(timezone.utc)
        cancelled_id = closed_loan(db, client_id, didactic_copy(db, book_id).id, seller_id, LoanStatus.CANCELLED,
                                   now, now + timedelta(days=30), None)
        db.commit()
    for kind in ('loans', 'returns'):
        for missing in (987654321, cancelled_id):
            response = http.get(f'{RECEIPTS}/{kind}/{missing}')
            assert (response.status_code, response.json()['code']) == (404, 'receipt_not_found')
        assert http.get(f'{RECEIPTS}/{kind}/0').status_code == 422
        assert http.get(f'{RECEIPTS}/{kind}/abc').status_code == 422
    assert http.get(f'{RECEIPTS}/sales/987654321').status_code == 404
    assert http.get(f'{RECEIPTS}/sales/0').status_code == 422


def test_client_reads_only_own_receipts_and_foreign_ones_look_missing(receipts):
    http, engine, book_id, client_id, seller_id = receipts
    loan_id, _ = request_pickup(http, engine, book_id, client_id)
    http.post(f'{BASE}/loans/{loan_id}/confirm-return')
    with Session(engine) as db:
        stranger = new_user(db, 'USER', 'Outro Cliente')
    before = counts(engine)

    as_user(client_id, 'USER')
    assert http.get(f'{RECEIPTS}/loans/{loan_id}').status_code == 200
    assert http.get(f'{RECEIPTS}/returns/{loan_id}').status_code == 200

    as_user(stranger, 'USER')
    foreign = http.get(f'{RECEIPTS}/loans/{loan_id}')
    absent = http.get(f'{RECEIPTS}/loans/987654321')
    assert (foreign.status_code, foreign.json()) == (absent.status_code, absent.json()) == (404, absent.json())
    assert http.get(f'{RECEIPTS}/returns/{loan_id}').status_code == 404
    assert counts(engine) == before  # somente leitura


def test_confirmed_sale_receipt_with_items_prices_total_and_ownership(receipts):
    http, engine, book_id, client_id, seller_id = receipts
    sessions = []
    app.dependency_overrides[get_sale_service] = sale_service(engine, sessions)
    first = new_commercial(engine, book_id, '37.50')
    second = new_commercial(engine, book_id, '12.25')
    created = http.post('/api/v1/sales/', json={'client_id': client_id, 'items': [{'copy_id': first}, {'copy_id': second}]})
    anonymous = http.post('/api/v1/sales/', json={'items': [{'copy_id': new_commercial(engine, book_id, '5.00')}]})
    assert created.status_code == 201 and anonymous.status_code == 201
    sale_id = created.json()['id']

    body = http.get(f'{RECEIPTS}/sales/{sale_id}').json()
    assert body['number'] == sale_id and body['total_amount'] == '49.75'
    assert [(i['copy_id'], i['unit_price']) for i in body['items']] == [(first, '37.50'), (second, '12.25')]
    assert body['items'][0]['book']['title'] == 'Livro integração' and body['items'][0]['copy_barcode'].startswith('V149-')
    assert body['client'] == {'id': client_id, 'name': 'Teste Cliente', 'code': None}
    assert body['employee']['id'] == seller_id
    with Session(engine) as db:
        assert datetime.fromisoformat(body['sale_date']) == db.get(Sale, sale_id).sale_date
    anon_body = http.get(f'{RECEIPTS}/sales/{anonymous.json()["id"]}').json()
    assert anon_body['client'] is None and anon_body['total_amount'] == '5.00'

    as_user(client_id, 'USER')
    assert http.get(f'{RECEIPTS}/sales/{sale_id}').status_code == 200
    assert http.get(f'{RECEIPTS}/sales/{anonymous.json()["id"]}').status_code == 404  # venda sem cliente
    with Session(engine) as db:
        stranger = new_user(db, 'USER', 'Outro Cliente')
    as_user(stranger, 'USER')
    assert http.get(f'{RECEIPTS}/sales/{sale_id}').status_code == 404
    for db in sessions:
        db.close()


def test_pending_or_cancelled_sale_has_no_receipt(receipts):
    http, engine, book_id, client_id, seller_id = receipts
    ids = {}
    with Session(engine) as db:
        db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(seller_id)})
        for status in (SaleStatus.PENDING, SaleStatus.CANCELLED):
            copy_id = new_commercial(engine, book_id, '9.90')
            sale = Sale(client_id=client_id, employee_id=seller_id, total_amount=9.90)
            db.add(sale)
            db.flush()
            db.add(SaleItem(sale_id=sale.id, copy_id=copy_id, unit_price=9.90))
            db.flush()
            sale.status = status
            db.flush()
            ids[status] = sale.id
        db.commit()
    for sale_id in ids.values():
        response = http.get(f'{RECEIPTS}/sales/{sale_id}')
        assert (response.status_code, response.json()['code']) == (404, 'receipt_not_found')
    as_user(client_id, 'USER')
    assert http.get(f'{RECEIPTS}/sales/{ids[SaleStatus.PENDING]}').status_code == 404


def test_authentication_roles_and_inactive_employee(receipts):
    http, engine, book_id, client_id, seller_id = receipts
    loan_id, _ = request_pickup(http, engine, book_id, client_id)
    app.dependency_overrides.pop(get_current_user)
    for path in (f'loans/{loan_id}', f'returns/{loan_id}', 'sales/1'):
        assert http.get(f'{RECEIPTS}/{path}').status_code == 401

    as_user(seller_id, 'STOCK_KEEPER')
    assert http.get(f'{RECEIPTS}/loans/{loan_id}').status_code == 403

    as_user(seller_id, 'SELLER')
    assert http.get(f'{RECEIPTS}/loans/{loan_id}').status_code == 200
    with Session(engine) as db:
        db.execute(update(Profile).where(Profile.id == seller_id).values(is_active=False))
        db.commit()
    for path in (f'loans/{loan_id}', f'returns/{loan_id}', 'sales/1'):
        response = http.get(f'{RECEIPTS}/{path}')
        assert (response.status_code, response.json()['code']) == (403, 'employee_record_required')
