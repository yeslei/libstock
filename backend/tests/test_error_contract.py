"""Contrato de erros (Issue #175): 422 sem eco de entrada, `code` estável em /copies, /sales e /loans,
venda com exemplar repetido, preço de exemplar comercial > 0 na inclusão. Sem banco: serviços com dublês."""
from decimal import Decimal
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.controllers.copy_controller import get_copy_service
from app.controllers.staff_desk_controller import get_staff_desk_service
from app.core.exceptions import ApplicationError, CopySalePriceRequiredError
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_book_service, get_loan_service, get_sale_service
from app.main import app
from app.models.domain import CopyStatus, DestinationType
from app.schemas.book_schema import BookCreate
from app.services.book_service import BookService
from app.services.copy_rules import require_commercial_price
from app.services.copy_service import CopyService
from app.services.loan_service import LoanService
from app.services.sale_service import SaleService
from app.services.staff_desk_service import StaffDeskService

SECRET = 'S3nh@-Secreta-NaoEcoar'
client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()


def as_user(*roles):
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=list(roles))


# ---- Item 3 e 4: 422 de validação sem eco de entrada e com código estável -----------------------

@pytest.mark.parametrize('path,payload', [
    ('/api/v1/auth/register', {'name': 'Ana', 'email': 'invalido', 'password': SECRET}),
    ('/api/v1/auth/register', {'name': 'A', 'email': 'ana@x.com', 'password': 'curta'}),
    ('/api/v1/auth/register', {'name': 'Ana', 'email': 'ana@x.com', 'password': SECRET[:4], 'role': SECRET}),
    ('/api/v1/auth/login', {'email': 'nao-e-email', 'password': SECRET}),
    ('/api/v1/auth/login', {'email': 'a@b.com', 'password': 12345}),
    ('/api/v1/auth/login', {'email': 'a@b.com', 'current_password': SECRET, SECRET: SECRET}),
])
def test_validation_error_never_echoes_input_in_any_route(path, payload):
    response = client.post(path, json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body['code'] == 'validation_error'
    assert isinstance(body['detail'], list) and body['detail']
    assert SECRET not in response.text and SECRET[:4] not in response.text
    assert 'curta' not in response.text and 'invalido' not in response.text
    for error in body['detail']:
        assert set(error) <= {'loc', 'msg', 'type'}  # sem `input` nem `ctx`


def test_unknown_field_name_is_hidden_at_any_depth():
    as_user('STOCK_KEEPER')
    payload = {'isbn': '9788575225530', 'initial_copy': {'barcode': 'X', 'destination': 'DIDACTIC', SECRET: 1}}
    response = client.post('/api/v1/books/', json=payload)
    assert response.status_code == 422 and SECRET not in response.text
    extra = next(e for e in response.json()['detail'] if e['type'] == 'extra_forbidden')
    assert extra['loc'] == ['body', 'initial_copy', 'campo_desconhecido']


def test_malformed_json_and_query_validation_keep_the_contract():
    as_user('SELLER')
    assert client.post('/api/v1/auth/login', content='{"password": "' + SECRET, headers={'content-type': 'application/json'}).status_code == 422
    response = client.get('/api/v1/staff/loans?limit=0')
    assert response.status_code == 422 and response.json()['code'] == 'validation_error'
    assert '"input"' not in response.text and '"ctx"' not in response.text


def test_reset_password_keeps_working_with_the_generalized_handler():
    as_user('ADMINISTRATOR')
    response = client.post('/api/v1/users/9/reset-password', json={'new_password': SECRET[:5]})
    assert response.status_code == 422 and SECRET[:5] not in response.text
    assert response.json()['code'] == 'validation_error'


# ---- Item 4: códigos de busca do balcão ---------------------------------------------------------

def desk_service():
    repository = MagicMock()
    repository.is_active_employee.return_value = True
    repository.search_clients.return_value = []
    repository.copy_lookup.return_value = []
    repository.free_commercial_counts.return_value = {}
    return StaffDeskService(MagicMock(), repository), repository


@pytest.mark.parametrize('path,code', [
    ('/api/v1/staff/clients?q=a', 'search_term_too_short'),
    ('/api/v1/staff/clients?q=', 'search_term_too_short'),
    ('/api/v1/staff/clients?q=%20%20', 'search_term_too_short'),
    ('/api/v1/staff/copies?q=', 'search_term_required'),
    ('/api/v1/staff/copies?q=%20', 'search_term_required'),
])
def test_search_term_errors_carry_stable_codes_in_the_common_case(path, code):
    service, repository = desk_service()
    app.dependency_overrides[get_staff_desk_service] = lambda: service
    as_user('SELLER')
    response = client.get(path)
    assert response.status_code == 422
    assert response.json()['code'] == code and isinstance(response.json()['detail'], str)
    repository.search_clients.assert_not_called()
    repository.copy_lookup.assert_not_called()


def test_valid_search_terms_still_reach_the_repository():
    service, repository = desk_service()
    app.dependency_overrides[get_staff_desk_service] = lambda: service
    as_user('SELLER')
    assert client.get('/api/v1/staff/clients?q=ana').status_code == 200
    assert client.get('/api/v1/staff/copies?q=LS-1').status_code == 200
    repository.search_clients.assert_called_once()


# ---- Item 1: venda com exemplar repetido --------------------------------------------------------

def sale_service(**overrides):
    repository = MagicMock()
    repository.client_active_state.return_value = True
    repository.lock_books_for_copies.return_value = {}
    repository.find_copies_for_sale.return_value = []
    repository.reserved_copy_ids.return_value = set()
    for name, value in overrides.items():
        setattr(repository, name, value)
    return SaleService(repository, MagicMock()), repository


def post_sale(service, items):
    app.dependency_overrides[get_sale_service] = lambda: service
    as_user('SELLER')
    return client.post('/api/v1/sales/', json={'client_id': 3, 'items': items})


def test_sale_with_repeated_copy_is_422_with_stable_code_and_touches_nothing():
    service, repository = sale_service()
    response = post_sale(service, [{'copy_id': 5}, {'copy_id': 6}, {'copy_id': 5}])
    assert response.status_code == 422
    assert response.json() == {'detail': 'A venda não pode repetir o mesmo exemplar nos itens.',
                               'code': 'duplicate_sale_item'}
    repository.client_active_state.assert_not_called()
    repository.create_sale.assert_not_called()


def test_sale_domain_errors_have_stable_codes():
    service, _ = sale_service()
    missing = post_sale(service, [{'copy_id': 5}])
    assert (missing.status_code, missing.json()['code']) == (404, 'copy_not_found')

    copy = NS(id=5, book_id=1, is_active=False, status=CopyStatus.AVAILABLE,
              destination=DestinationType.COMMERCIAL, sale_price=Decimal('10'))
    service, _ = sale_service(find_copies_for_sale=MagicMock(return_value=[copy]),
                              lock_books_for_copies=MagicMock(return_value={1: NS(is_active=True)}))
    response = post_sale(service, [{'copy_id': 5}])
    assert (response.status_code, response.json()['code']) == (404, 'copy_inactive')
    copy.is_active, copy.status = True, CopyStatus.SOLD
    response = post_sale(service, [{'copy_id': 5}])
    assert (response.status_code, response.json()['code']) == (409, 'copy_not_available')
    copy.status, copy.destination = CopyStatus.AVAILABLE, DestinationType.DIDACTIC
    response = post_sale(service, [{'copy_id': 5}])
    assert (response.status_code, response.json()['code']) == (409, 'copy_not_for_sale')


@pytest.mark.parametrize('error,status,code', [
    (IntegrityError('x', {}, Exception('x')), 409, 'sale_conflict'),
    (SQLAlchemyError('x'), 500, 'sale_persistence_error'),
])
def test_sale_persistence_failures_have_codes_and_roll_back(error, status, code):
    copy = NS(id=5, book_id=1, is_active=True, status=CopyStatus.AVAILABLE,
              destination=DestinationType.COMMERCIAL, sale_price=Decimal('10'))
    service, repository = sale_service(find_copies_for_sale=MagicMock(return_value=[copy]),
                                       lock_books_for_copies=MagicMock(return_value={1: NS(is_active=True)}),
                                       create_sale=MagicMock(side_effect=error))
    response = post_sale(service, [{'copy_id': 5}])
    assert (response.status_code, response.json()['code']) == (status, code)
    service.db.rollback.assert_called_once_with()


# ---- Item 4: empréstimos ------------------------------------------------------------------------

def loan_service(copy=None, book=None, **overrides):
    repository = MagicMock()
    repository.lock_book_for_copy.return_value = book
    repository.find_copy_for_loan.return_value = copy
    for name, value in overrides.items():
        setattr(repository, name, value)
    return LoanService(repository, MagicMock(), MagicMock()), repository


def post_loan(service):
    app.dependency_overrides[get_loan_service] = lambda: service
    as_user('SELLER')
    return client.post('/api/v1/loans/', json={'client_id': 3, 'copy_id': 5})


def test_loan_domain_errors_have_stable_codes():
    service, _ = loan_service()
    response = post_loan(service)
    assert (response.status_code, response.json()['code']) == (404, 'copy_not_found')
    copy = NS(id=5, status=CopyStatus.BORROWED, destination=DestinationType.DIDACTIC)
    service, _ = loan_service(copy, NS(is_active=True))
    response = post_loan(service)
    assert (response.status_code, response.json()['code']) == (409, 'copy_not_available')
    copy.status = CopyStatus.AVAILABLE
    copy.destination = DestinationType.COMMERCIAL
    assert post_loan(service).json()['code'] == 'copy_not_for_loan'


@pytest.mark.parametrize('error,status,code', [
    (IntegrityError('x', {}, Exception('x')), 409, 'loan_conflict'),
    (SQLAlchemyError('x'), 500, 'loan_persistence_error'),
])
def test_loan_persistence_failures_have_codes(error, status, code):
    copy = NS(id=5, status=CopyStatus.AVAILABLE, destination=DestinationType.DIDACTIC)
    service, _ = loan_service(copy, NS(is_active=True), create_loan=MagicMock(side_effect=error))
    response = post_loan(service)
    assert (response.status_code, response.json()['code']) == (status, code)
    service.db.rollback.assert_called_once_with()


def test_loan_return_errors_have_stable_codes():
    def patch(service):
        app.dependency_overrides[get_loan_service] = lambda: service
        as_user('SELLER')
        return client.patch('/api/v1/loans/9/return')

    service, repository = loan_service()
    repository.find_loan_for_return.return_value = None
    response = patch(service)
    assert (response.status_code, response.json()['code']) == (404, 'loan_not_found')
    repository.find_loan_for_return.return_value = NS(status='RETURNED', copy_id=5)
    response = patch(service)
    assert (response.status_code, response.json()['code']) == (409, 'loan_already_closed')


# ---- Item 4: exemplares -------------------------------------------------------------------------

def copy_service(**overrides):
    repository = MagicMock()
    repository.is_employee.return_value = True
    for name, value in overrides.items():
        setattr(repository, name, value)
    db = MagicMock()
    db.get.return_value = NS(is_active=True)
    return CopyService(repository, db), repository, db


def post_copy(service, **payload):
    app.dependency_overrides[get_copy_service] = lambda: service
    as_user('STOCK_KEEPER')
    body = {'book_id': 4, 'barcode': 'LS-1', 'destination': 'DIDACTIC', **payload}
    return client.post('/api/v1/copies/', json=body)


def test_copy_creation_errors_have_stable_codes():
    service, _, db = copy_service()
    db.get.return_value = None
    response = post_copy(service)
    assert (response.status_code, response.json()['code']) == (404, 'book_not_found')
    assert response.json()['detail'] == 'Obra não encontrada ou inativa.'

    service, repository, db = copy_service(create_copy=MagicMock(side_effect=IntegrityError('x', {}, Exception('x'))))
    response = post_copy(service)
    assert (response.status_code, response.json()['code']) == (409, 'duplicate_barcode')
    assert response.json()['detail'] == 'Já existe um exemplar com este código de barras.'

    service, _, _ = copy_service(create_copy=MagicMock(side_effect=RuntimeError('boom')))
    response = post_copy(service)
    assert (response.status_code, response.json()['code']) == (500, 'copy_persistence_error')


def test_copy_batch_errors_have_stable_codes():
    service, _, _ = copy_service(create_copies=MagicMock(side_effect=RuntimeError('boom')))
    app.dependency_overrides[get_copy_service] = lambda: service
    as_user('STOCK_KEEPER')
    body = {'copies': [{'book_id': 4, 'barcode': 'LS-1', 'destination': 'DIDACTIC'}]}
    response = client.post('/api/v1/copies/batch', json=body)
    assert (response.status_code, response.json()['code']) == (500, 'copy_persistence_error')
    assert response.json()['detail'] == 'Não foi possível cadastrar os exemplares.'


# ---- Item 2: preço > 0 na inclusão, igual à edição ----------------------------------------------

@pytest.mark.parametrize('price', [None, 0, Decimal('0.00')])
def test_commercial_copy_requires_positive_price_on_creation_with_the_edit_code_and_message(price):
    with pytest.raises(CopySalePriceRequiredError) as error:
        require_commercial_price(DestinationType.COMMERCIAL, price)
    assert (error.value.status_code, error.value.code) == (422, 'copy_sale_price_required')
    assert error.value.message == 'Exemplar destinado à venda exige preço de venda maior que zero.'
    require_commercial_price(DestinationType.COMMERCIAL, Decimal('0.01'))
    require_commercial_price(DestinationType.DIDACTIC, None)


@pytest.mark.parametrize('price', [None, 0])
def test_post_copies_rejects_zero_or_missing_price(price):
    service, repository, _ = copy_service()
    payload = {'destination': 'COMMERCIAL'}
    if price is not None:
        payload['sale_price'] = price
    response = post_copy(service, **payload)
    assert response.status_code == 422
    assert response.json() == {'detail': 'Exemplar destinado à venda exige preço de venda maior que zero.',
                               'code': 'copy_sale_price_required'}
    repository.create_copy.assert_not_called()


def test_post_copies_accepts_a_positive_price():
    service, repository, _ = copy_service()
    repository.create_copy.return_value = NS(id=1, book_id=4, barcode='LS-1', destination='COMMERCIAL',
                                             condition=None, sale_price=Decimal('9.90'), acquired_at=None,
                                             status='AVAILABLE', is_active=True)
    assert post_copy(service, destination='COMMERCIAL', sale_price=9.9).status_code == 201


def test_batch_with_a_zero_price_item_creates_nothing():
    service, repository, _ = copy_service()
    app.dependency_overrides[get_copy_service] = lambda: service
    as_user('STOCK_KEEPER')
    body = {'copies': [{'book_id': 4, 'barcode': 'A', 'destination': 'DIDACTIC'},
                       {'book_id': 4, 'barcode': 'B', 'destination': 'COMMERCIAL', 'sale_price': 0}]}
    response = client.post('/api/v1/copies/batch', json=body)
    assert (response.status_code, response.json()['code']) == (422, 'copy_sale_price_required')
    repository.create_copies.assert_not_called()


@pytest.mark.parametrize('price', [None, 0])
def test_post_books_rejects_zero_or_missing_initial_copy_price(price):
    repository = MagicMock()
    repository.employee_exists.return_value = True
    service = BookService(db=MagicMock(), repository=repository)
    service.fetch_google_books_data = AsyncMock(return_value={})
    app.dependency_overrides[get_book_service] = lambda: service
    as_user('STOCK_KEEPER')
    initial = {'barcode': 'LS-9', 'destination': 'COMMERCIAL'}
    if price is not None:
        initial['sale_price'] = price
    response = client.post('/api/v1/books/', json={'isbn': '9788575225530', 'title': 'T', 'author': 'A',
                                                    'initial_copy': initial})
    assert response.status_code == 422
    assert response.json()['code'] == 'copy_sale_price_required'
    repository.create_book.assert_not_called()
    service.fetch_google_books_data.assert_not_awaited()


def test_book_schema_still_rejects_negative_price_as_validation_error():
    with pytest.raises(ValueError):
        BookCreate(isbn='9788575225530', initial_copy={'barcode': 'X', 'destination': 'COMMERCIAL', 'sale_price': -1})


def test_application_error_exposes_detail_alias():
    assert ApplicationError('m', 'c', 400).detail == 'm'
