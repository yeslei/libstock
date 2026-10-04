"""Venda direta confirmada no ato (Issue #149) contra PostgreSQL descartável migrado pelo Alembic."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.dependencies.services import get_sale_service
from app.main import app
from app.models.domain import Book, Client, Copy, CopyStatus, DestinationType, Sale, SaleItem, SaleStatus
from app.repositories.sale_repository import SaleRepository
from app.models.domain import Profile
from app.models.user import User
from app.schemas.sale_schema import SaleCreate
from app.services.sale_service import SaleService
from test_client_requests_postgres import records  # noqa: F401  (fixture)
from test_staff_desk_postgres import commercial_copy, desk, didactic_copy, new_user  # noqa: F401  (fixtures)

URL = '/api/v1/sales/'


def sale_service(engine, sessions):
    def factory():
        db = Session(engine)
        sessions.append(db)
        return SaleService(SaleRepository(db), db)
    return factory


def new_commercial(engine, book_id, price):
    with Session(engine) as db:
        db.execute(text("SELECT set_config('libstock.employee_id', "
                        "(SELECT id::text FROM employees LIMIT 1), true)"))
        copy = Copy(book_id=book_id, barcode='V149-' + uuid4().hex[:12],
                    destination=DestinationType.COMMERCIAL, sale_price=price)
        db.add(copy)
        db.commit()
        return copy.id


def test_direct_sale_is_confirmed_and_copy_becomes_sold_with_catalog_price(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    sessions = []
    app.dependency_overrides[get_sale_service] = sale_service(engine, sessions)
    copy_id = new_commercial(engine, book_id, '37.50')
    # O valor enviado (0.01) é ignorado: vale o preço cadastrado no exemplar.
    response = http.post(URL, json={'client_id': client_id, 'items': [{'copy_id': copy_id, 'unit_price': '0.01'}]})
    assert response.status_code == 201
    body = response.json()
    assert body['status'] == 'CONFIRMED' and body['employee_id'] == seller_id
    assert body['total_amount'] == '37.50' and [i['unit_price'] for i in body['items']] == ['37.50']
    with Session(engine) as db:
        assert db.get(Copy, copy_id).status == CopyStatus.SOLD
        sale = db.get(Sale, body['id'])
        assert sale.status == SaleStatus.CONFIRMED and str(sale.total_amount) == '37.50'
        # Auditoria: a mudança do exemplar para SOLD registra o funcionário responsável.
        audit = db.execute(text("SELECT employee_id, new_value->>'status' FROM audit_logs "
                                "WHERE entity_type = 'copies' AND entity_id = :id AND new_value->>'status' = 'SOLD'"),
                           {'id': str(copy_id)}).all()
        assert audit == [(seller_id, 'SOLD')]
        assert db.scalar(select(func.count()).select_from(SaleItem).where(SaleItem.sale_id == sale.id)) == 1
    for db in sessions:
        db.close()


def test_direct_sale_without_price_in_request_and_customer(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    sessions = []
    app.dependency_overrides[get_sale_service] = sale_service(engine, sessions)
    copy_id = new_commercial(engine, book_id, '12.00')
    response = http.post(URL, json={'client_id': client_id, 'items': [{'copy_id': copy_id}]})
    assert response.status_code == 201
    assert (response.json()['client_id'], response.json()['total_amount']) == (client_id, '12.00')
    for db in sessions:
        db.close()


def test_direct_sale_blocks_didactic_unavailable_and_inactive_book(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    sessions = []
    app.dependency_overrides[get_sale_service] = sale_service(engine, sessions)
    with Session(engine) as db:
        didactic_id = didactic_copy(db, book_id).id
        sales_before = db.scalar(select(func.count()).select_from(Sale))
    refused = http.post(URL, json={'client_id': client_id, 'items': [{'copy_id': didactic_id}]})
    assert refused.status_code == 409
    sold_id = new_commercial(engine, book_id, '10.00')
    assert http.post(URL, json={'client_id': client_id, 'items': [{'copy_id': sold_id}]}).status_code == 201
    again = http.post(URL, json={'client_id': client_id, 'items': [{'copy_id': sold_id}]})
    assert again.status_code == 409
    free_id = new_commercial(engine, book_id, '11.00')
    with Session(engine) as db:
        db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(seller_id)})
        db.get(Book, book_id).is_active = False
        db.commit()
    inactive = http.post(URL, json={'client_id': client_id, 'items': [{'copy_id': free_id}]})
    assert (inactive.status_code, inactive.json()['code']) == (409, 'book_inactive')
    with Session(engine) as db:
        assert db.get(Copy, free_id).status == CopyStatus.AVAILABLE
        assert db.get(Copy, didactic_id).status == CopyStatus.AVAILABLE
        assert db.scalar(select(func.count()).select_from(Sale)) == sales_before + 1  # só a venda do exemplar vendido
    for db in sessions:
        db.close()


def test_concurrent_direct_sales_of_same_copy_only_one_wins(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    copy_id = new_commercial(engine, book_id, '19.90')
    barrier = Barrier(2)

    def attempt(_):
        with Session(engine) as db:
            service = SaleService(SaleRepository(db), db)
            barrier.wait(timeout=10)
            try:
                service.create_sale(SaleCreate(client_id=client_id, items=[{'copy_id': copy_id}]), employee_id=seller_id)
                return 201
            except Exception as error:  # noqa: BLE001
                return getattr(error, 'status_code', repr(error))

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))
    assert sorted(results) == [201, 409]
    with Session(engine) as db:
        assert db.get(Copy, copy_id).status == CopyStatus.SOLD
        assert db.scalar(select(func.count()).select_from(SaleItem).where(SaleItem.copy_id == copy_id)) == 1


def test_direct_sale_requires_an_existing_active_client_but_accepts_a_penalized_one(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    sessions = []
    app.dependency_overrides[get_sale_service] = sale_service(engine, sessions)
    copy_id = new_commercial(engine, book_id, '14.00')
    with Session(engine) as db:
        sales_before = db.scalar(select(func.count()).select_from(Sale))
        inactive_user = new_user(db, 'USER', 'Cliente Usuário Inativo')
        inactive_profile = new_user(db, 'USER', 'Cliente Perfil Inativo')
        db.get(User, inactive_user).is_active = False
        db.get(Profile, inactive_profile).is_active = False
        db.get(Client, client_id).is_penalized = True
        db.commit()
    items = [{'copy_id': copy_id}]
    assert http.post(URL, json={'items': items}).status_code == 422  # contrato: client_id é obrigatório
    assert http.post(URL, json={'client_id': None, 'items': items}).status_code == 422
    unknown = http.post(URL, json={'client_id': 2147483000, 'items': items})
    assert (unknown.status_code, unknown.json()['code']) == (404, 'client_not_found')
    for refused_id in (inactive_user, inactive_profile):
        refused = http.post(URL, json={'client_id': refused_id, 'items': items})
        assert (refused.status_code, refused.json()['code']) == (403, 'client_inactive')
    staff = http.post(URL, json={'client_id': seller_id, 'items': items})
    assert (staff.status_code, staff.json()['code']) == (404, 'client_not_found')  # funcionário não é cliente
    with Session(engine) as db:
        assert db.get(Copy, copy_id).status == CopyStatus.AVAILABLE
        assert db.scalar(select(func.count()).select_from(Sale)) == sales_before
    # Penalidade não bloqueia a venda: o pagamento é feito no balcão.
    accepted = http.post(URL, json={'client_id': client_id, 'items': items})
    assert (accepted.status_code, accepted.json()['client_id'], accepted.json()['status']) == (201, client_id, 'CONFIRMED')
    with Session(engine) as db:
        assert db.get(Copy, copy_id).status == CopyStatus.SOLD
    for db in sessions:
        db.close()
