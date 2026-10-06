"""Consultas de acervo do balcão (somente leitura): contrato, papéis, entrada e regras do service."""
from decimal import Decimal
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.controllers.staff_desk_controller import get_staff_desk_service
from app.core.exceptions import ApplicationError
from app.dependencies.authentication import get_current_user
from app.main import app
from app.models.domain import CopyStatus, DestinationType
from app.repositories.staff_desk_repository import StaffDeskRepository
from app.services.staff_desk_service import StaffDeskService

PATHS = ['/api/v1/staff/books', '/api/v1/staff/books/3', '/api/v1/staff/copies?q=abc']
METHODS = ['catalog_books', 'catalog_book', 'copy_lookup']


@pytest.fixture
def api():
    fake = Mock()
    fake.catalog_books.return_value = []
    fake.copy_lookup.return_value = []
    app.dependency_overrides[get_staff_desk_service] = lambda: fake
    yield TestClient(app), fake
    app.dependency_overrides.clear()


@pytest.mark.parametrize('path', PATHS)
def test_requires_authentication(api, path):
    client, _ = api
    assert client.get(path).status_code == 401


@pytest.mark.parametrize('path', PATHS)
def test_client_role_is_denied(api, path):
    client, fake = api
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=['USER'])
    assert client.get(path).status_code == 403
    for name in METHODS:
        getattr(fake, name).assert_not_called()


def test_copy_lookup_stays_denied_to_stock_keeper(api):
    client, fake = api
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=['STOCK_KEEPER'])
    assert client.get('/api/v1/staff/copies?q=abc').status_code == 403
    fake.copy_lookup.assert_not_called()


def test_stock_keeper_reads_catalog_books_only(api):
    """Issue #169: o estoquista consulta obras no balcão, sem acesso ao restante de /staff."""
    client, fake = api
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=['STOCK_KEEPER'])
    assert client.get('/api/v1/staff/books?q=dom').status_code == 200
    fake.catalog_books.assert_called_once_with(7, 'dom', 50)
    fake.catalog_book.return_value = {'id': 3, 'title': 'T', 'author': 'A', 'isbn': None, 'genre': None, 'is_active': True,
                                      'total_copies': 0, 'didactic_copies': 0, 'commercial_copies': 0, 'copies': []}
    assert client.get('/api/v1/staff/books/3').status_code == 200
    fake.catalog_book.assert_called_once_with(7, 3)


@pytest.mark.parametrize('role', ['SELLER', 'ADMINISTRATOR'])
def test_counter_roles_can_read_lists(api, role):
    client, fake = api
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=[role])
    assert client.get('/api/v1/staff/books?q=dom&limit=5').json() == []
    fake.catalog_books.assert_called_once_with(7, 'dom', 5)
    assert client.get('/api/v1/staff/copies?q=0010').json() == []
    fake.copy_lookup.assert_called_once_with(7, '0010', 20, destination=None, available=None)
    fake.copy_lookup.reset_mock()
    assert client.get('/api/v1/staff/copies?destination=DIDACTIC&available=true&limit=100').json() == []
    fake.copy_lookup.assert_called_once_with(7, None, 100, destination=DestinationType.DIDACTIC, available=True)


@pytest.mark.parametrize('path', [
    '/api/v1/staff/books?limit=0', '/api/v1/staff/books?limit=101', '/api/v1/staff/books?q=' + 'x' * 101,
    '/api/v1/staff/books/0', '/api/v1/staff/books/abc', '/api/v1/staff/copies?destination=OTHER',
    '/api/v1/staff/copies?available=maybe', '/api/v1/staff/copies?limit=101',
    '/api/v1/staff/copies?q=' + 'x' * 101,
])
def test_invalid_input_is_rejected(api, path):
    client, fake = api
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=['SELLER'])
    assert client.get(path).status_code == 422
    for name in METHODS:
        getattr(fake, name).assert_not_called()


def make_service():
    repo = Mock(spec=StaffDeskRepository)
    repo.is_active_employee.return_value = True
    repo.book_genres.return_value = {}
    return StaffDeskService(Mock(), repo), repo


BOOK = NS(id=1, title='Dom Casmurro', author='Machado', isbn='9780000000002', genre='Romance', is_active=True)


def book_row(**counts):
    return {'Book': BOOK, 'total_copies': 4, 'didactic_copies': 3, 'commercial_copies': 1, **counts}


@pytest.mark.parametrize('method,args', [('catalog_books', (7, None, 50)), ('catalog_book', (7, 1)),
                                         ('copy_lookup', (7, 'abc', 20))])
def test_inactive_employee_is_denied_without_querying(method, args):
    service, repo = make_service()
    repo.is_active_employee.return_value = False
    with pytest.raises(ApplicationError) as error:
        getattr(service, method)(*args)
    assert (error.value.status_code, error.value.code) == (403, 'employee_record_required')
    for name in ('catalog_books', 'catalog_book', 'book_copies', 'copy_lookup'):
        getattr(repo, name).assert_not_called()


def test_catalog_list_maps_counts_and_trims_term():
    service, repo = make_service()
    repo.catalog_books.return_value = [book_row()]
    result = service.catalog_books(7, '  dom ', 50)
    repo.catalog_books.assert_called_once_with('dom', 50)
    assert result[0].model_dump() == {
        'id': 1, 'title': 'Dom Casmurro', 'author': 'Machado', 'isbn': '9780000000002', 'genre': 'Romance',
        'genres': [], 'is_active': True, 'total_copies': 4, 'didactic_copies': 3, 'commercial_copies': 1, 'available_didactic': 0, 'available_commercial': 0, 'cover_url': None}


def test_catalog_list_and_detail_expose_catalog_genres():
    """Issue #174: o balcão exibe as categorias do catálogo (book_genres), não só o texto legado."""
    service, repo = make_service()
    genres = {1: [{'id': 2, 'name': 'Não ficção', 'slug': 'nao-ficcao'}, {'id': 7, 'name': 'Romance', 'slug': 'romance'}]}
    repo.book_genres.return_value = genres
    repo.catalog_books.return_value = [book_row()]
    repo.catalog_book.return_value = book_row()
    repo.book_copies.return_value = []
    assert [g.name for g in service.catalog_books(7, None, 50)[0].genres] == ['Não ficção', 'Romance']
    assert [g.slug for g in service.catalog_book(7, 1).genres] == ['nao-ficcao', 'romance']
    repo.book_genres.assert_called_with([1])


def test_catalog_detail_unknown_book_is_404():
    service, repo = make_service()
    repo.catalog_book.return_value = None
    with pytest.raises(ApplicationError) as error:
        service.catalog_book(7, 99)
    assert (error.value.status_code, error.value.code) == (404, 'book_not_found')
    repo.book_copies.assert_not_called()


def copy(id, destination, *, price=None, status=CopyStatus.AVAILABLE, active=True):
    return NS(id=id, barcode=f'C{id}', destination=destination, status=status, condition=None, sale_price=price,
              is_active=active)


def test_catalog_detail_exposes_copies_with_availability_flags():
    service, repo = make_service()
    repo.catalog_book.return_value = book_row()
    repo.book_copies.return_value = [
        {'Copy': copy(1, DestinationType.DIDACTIC), 'free': True, 'allocated_for_purchase': False},
        {'Copy': copy(2, DestinationType.COMMERCIAL, price=Decimal('38.90')), 'free': False,
         'allocated_for_purchase': True},
    ]
    detail = service.catalog_book(7, 1)
    assert [(c.barcode, c.free, c.allocated_for_purchase) for c in detail.copies] == [
        ('C1', True, False), ('C2', False, True)]
    assert detail.copies[1].sale_price == Decimal('38.90') and detail.total_copies == 4


def lookup_row(copy, free):
    return {'Copy': copy, 'Book': NS(id=1, title='Sapiens', author='Harari', isbn=None, is_active=True), 'free': free}


@pytest.mark.parametrize('term', ['', '   '])
def test_lookup_requires_term(term):
    service, repo = make_service()
    with pytest.raises(ApplicationError) as error:
        service.copy_lookup(7, term, 20)
    assert (error.value.status_code, error.value.code) == (422, 'search_term_required')
    repo.copy_lookup.assert_not_called()


def test_lookup_without_term_lists_and_forwards_filters():
    service, repo = make_service()
    repo.copy_lookup.return_value = [lookup_row(copy(1, DestinationType.COMMERCIAL, price=Decimal('38.90')), True)]
    repo.free_commercial_counts.return_value = {1: 1}
    result = service.copy_lookup(7, None, 20, destination=DestinationType.COMMERCIAL, available=True)
    repo.copy_lookup.assert_called_once_with(None, 20, DestinationType.COMMERCIAL, True)
    assert [i.sellable for i in result] == [True]


def test_lookup_decides_sale_block_in_backend():
    service, repo = make_service()
    repo.copy_lookup.return_value = [
        lookup_row(copy(1, DestinationType.COMMERCIAL, price=Decimal('38.90')), True),
        lookup_row(copy(2, DestinationType.DIDACTIC), True),
        lookup_row(copy(3, DestinationType.COMMERCIAL, price=Decimal('10.00')), False),
    ]
    repo.free_commercial_counts.return_value = {1: 1}
    result = service.copy_lookup(7, ' 00 ', 20)
    repo.copy_lookup.assert_called_once_with('00', 20, None, None)
    assert [(i.sellable, i.sale_block_reason) for i in result] == [
        (True, None), (False, 'DIDACTIC'), (False, 'NOT_AVAILABLE')]
    assert all(i.free_commercial_copies == 1 for i in result)
    assert result[0].sale_price == Decimal('38.90')


@pytest.mark.parametrize('method,args,target', [
    ('catalog_books', (7, None, 50), 'catalog_books'), ('catalog_book', (7, 1), 'catalog_book'),
    ('copy_lookup', (7, 'abc', 20), 'copy_lookup')])
def test_query_failure_is_normalized(method, args, target):
    service, repo = make_service()
    getattr(repo, target).side_effect = SQLAlchemyError('internal database details')
    with pytest.raises(ApplicationError) as error:
        getattr(service, method)(*args)
    assert (error.value.status_code, error.value.code) == (500, 'desk_query_error')
    assert 'internal database' not in error.value.message
