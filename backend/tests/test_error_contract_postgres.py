"""Correções da Issue #175 contra PostgreSQL descartável migrado pelo Alembic: venda com exemplar repetido,
preço de exemplar comercial na inclusão, 422 sem eco e destaque com as ofertas reais."""
from unittest.mock import AsyncMock
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.dependencies.services import get_book_service, get_catalog_service, get_sale_service
from app.main import app
from app.models.domain import Copy, CopyStatus, DestinationType, SaleItem
from app.repositories.book_repository import BookRepository
from app.repositories.catalog_repository import CatalogRepository, GenreRepository
from app.services.book_service import BookService
from app.services.catalog_service import CatalogService
from test_acervo_seller_postgres import acervo  # noqa: F401  (fixture)
from test_client_requests_postgres import records  # noqa: F401  (fixture)
from test_direct_sale_postgres import URL, new_commercial, sale_service
from test_staff_desk_postgres import desk  # noqa: F401  (fixtures)


def test_sale_with_repeated_copy_is_422_and_persists_nothing_instead_of_500(desk):  # noqa: F811
    http, engine, book_id, client_id, _ = desk
    sessions = []
    app.dependency_overrides[get_sale_service] = sale_service(engine, sessions)
    copy_id = new_commercial(engine, book_id, '20.00')
    response = http.post(URL, json={'client_id': client_id, 'items': [{'copy_id': copy_id}, {'copy_id': copy_id}]})
    assert response.status_code == 422
    assert response.json() == {'detail': 'A venda não pode repetir o mesmo exemplar nos itens.',
                               'code': 'duplicate_sale_item'}
    with Session(engine) as db:
        assert db.get(Copy, copy_id).status == CopyStatus.AVAILABLE
        assert db.scalar(select(func.count()).select_from(SaleItem).where(SaleItem.copy_id == copy_id)) == 0
    # A venda sem repetição do mesmo exemplar continua funcionando.
    ok = http.post(URL, json={'client_id': client_id, 'items': [{'copy_id': copy_id}]})
    assert ok.status_code == 201
    again = http.post(URL, json={'client_id': client_id, 'items': [{'copy_id': copy_id}]})
    assert again.status_code == 409 and again.json()['code'] == 'copy_not_available'
    for db in sessions:
        db.close()


def test_sale_domain_errors_carry_codes_against_the_real_database(desk):  # noqa: F811
    http, engine, book_id, client_id, _ = desk
    sessions = []
    app.dependency_overrides[get_sale_service] = sale_service(engine, sessions)
    missing = http.post(URL, json={'client_id': client_id, 'items': [{'copy_id': 987654321}]})
    assert (missing.status_code, missing.json()['code']) == (404, 'copy_not_found')
    with Session(engine) as db:
        didactic = db.scalar(select(Copy.id).where(Copy.book_id == book_id,
                                                   Copy.destination == DestinationType.DIDACTIC))
    refused = http.post(URL, json={'client_id': client_id, 'items': [{'copy_id': didactic}]})
    assert (refused.status_code, refused.json()['code']) == (409, 'copy_not_for_sale')
    for db in sessions:
        db.close()


def test_copy_and_book_creation_reject_zero_price_and_edit_uses_the_same_code(acervo):  # noqa: F811
    http, engine = acervo.http, acervo.engine
    barcode = 'P175-' + uuid4().hex[:10]
    for price in (None, 0, '0.00'):
        payload = {'book_id': acervo.book_id, 'barcode': barcode, 'destination': 'COMMERCIAL'}
        if price is not None:
            payload['sale_price'] = price
        response = http.post('/api/v1/copies/', json=payload)
        assert (response.status_code, response.json()['code']) == (422, 'copy_sale_price_required'), price
    with engine.connect() as conn:
        assert conn.scalar(text('SELECT count(*) FROM copies WHERE barcode = :b'), {'b': barcode}) == 0
    ok = http.post('/api/v1/copies/', json={'book_id': acervo.book_id, 'barcode': barcode,
                                            'destination': 'COMMERCIAL', 'sale_price': '0.01'})
    assert ok.status_code == 201
    edit = http.patch('/api/v1/copies/' + str(ok.json()['id']), json={'sale_price': 0})
    assert (edit.status_code, edit.json()['code']) == (422, 'copy_sale_price_required')
    duplicate = http.post('/api/v1/copies/', json={'book_id': acervo.book_id, 'barcode': barcode,
                                                   'destination': 'COMMERCIAL', 'sale_price': 5})
    assert (duplicate.status_code, duplicate.json()['code']) == (409, 'duplicate_barcode')

    def book_service():
        db = Session(engine)
        service = BookService(db=db, repository=BookRepository(db))
        service.fetch_google_books_data = AsyncMock(return_value={})
        return service

    app.dependency_overrides[get_book_service] = book_service
    isbn = '9788575225530'
    for price in (None, 0):
        initial = {'barcode': 'B175-' + uuid4().hex[:8], 'destination': 'COMMERCIAL'}
        if price is not None:
            initial['sale_price'] = price
        response = http.post('/api/v1/books/', json={'isbn': isbn, 'title': 'T', 'author': 'A',
                                                      'initial_copy': initial})
        assert (response.status_code, response.json()['code']) == (422, 'copy_sale_price_required')
    with engine.connect() as conn:
        assert conn.scalar(text('SELECT count(*) FROM books WHERE isbn = :i'), {'i': isbn}) == 0


def test_validation_422_does_not_echo_the_password_on_the_real_app(desk):  # noqa: F811
    http = desk[0]
    secret = 'Seg3gred0!Digitado'
    response = http.post('/api/v1/auth/register', json={'name': 'A', 'email': 'ruim', 'password': secret})
    assert response.status_code == 422 and secret not in response.text
    assert response.json()['code'] == 'validation_error'


def test_featured_patch_returns_the_real_offers_of_the_book(acervo):  # noqa: F811
    http, engine = acervo.http, acervo.engine
    db = Session(engine)
    app.dependency_overrides[get_catalog_service] = lambda: CatalogService(
        db=db, catalog_repository=CatalogRepository(db), genre_repository=GenreRepository(db))
    acervo.state.roles = ['ADMINISTRATOR']
    response = http.patch('/api/v1/admin/books/' + str(acervo.book_id) + '/featured',
                          json={'is_featured': True, 'position': 2})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['id'] == acervo.book_id
    assert {offer['destination'] for offer in body['offers']} == {'COMMERCIAL', 'DIDACTIC'}
    commercial = next(o for o in body['offers'] if o['destination'] == 'COMMERCIAL')
    assert commercial['available'] is True and commercial['price'] == '25.00'
    public = http.get('/api/v1/catalog/books/' + str(acervo.book_id)).json()
    assert body['offers'] == public['offers']  # mesma projeção do catálogo público
    off = http.patch('/api/v1/admin/books/' + str(acervo.book_id) + '/featured', json={'is_featured': False})
    assert off.status_code == 200 and off.json()['offers'] == body['offers']
    db.close()
