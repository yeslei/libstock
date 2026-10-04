"""Categorias da obra (Issue #174): schema e service sem banco."""
from types import SimpleNamespace as NS
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.core.exceptions import GenreNotFoundError
from app.schemas.book_schema import BookCreate, BookResponse, BookUpdate
from app.services.book_service import BookService

COPY = {'barcode': 'EX-1', 'destination': 'DIDACTIC'}


def genre(id, name):
    return NS(id=id, name=name, slug=name.lower())


def service(found=()):
    repository = MagicMock()
    repository.find_genres_by_ids.return_value = list(found)
    return BookService(db=MagicMock(), repository=repository), repository


def test_genre_ids_are_optional_deduplicated_and_ordered():
    assert BookCreate(isbn='9788575225530', initial_copy=COPY).genre_ids is None
    assert BookCreate(isbn='9788575225530', genre_ids=[3, 1, 3, 2], initial_copy=COPY).genre_ids == [3, 1, 2]
    assert BookUpdate(genre_ids=[]).genre_ids == []


@pytest.mark.parametrize('value', [[0], [-1], [2**63], list(range(1, 22))])
def test_invalid_genre_ids_are_rejected(value):
    with pytest.raises(ValidationError):
        BookCreate(isbn='9788575225530', genre_ids=value, initial_copy=COPY)
    with pytest.raises(ValidationError):
        BookUpdate(genre_ids=value)


def test_update_rejects_null_genre_ids_but_accepts_genre_ids_as_the_only_change():
    with pytest.raises(ValidationError):
        BookUpdate(genre_ids=None)
    assert BookUpdate(genre_ids=[1]).model_fields_set == {'genre_ids'}


def test_missing_ids_raise_404_with_details_in_requested_order():
    svc, _ = service([genre(1, 'Romance')])
    with pytest.raises(GenreNotFoundError) as error:
        svc._resolve_genres([9, 1, 7])
    assert (error.value.status_code, error.value.code) == (404, 'genre_not_found')
    assert error.value.details == {'missing_ids': [9, 7]}


def test_resolve_keeps_the_requested_order():
    svc, _ = service([genre(1, 'Romance'), genre(2, 'Fantasia')])
    assert [g.id for g in svc._resolve_genres([2, 1])] == [2, 1]
    assert BookService.genre_text([genre(2, 'Fantasia'), genre(1, 'Romance')]) == 'Fantasia, Romance'


def test_genre_text_is_none_when_empty_and_fits_in_100_characters():
    assert BookService.genre_text([]) is None
    names = [genre(i, 'Categoria longa número ' + str(i) * 5) for i in range(1, 6)]
    text = BookService.genre_text(names)
    assert text is not None and len(text) <= 100 and text.startswith(names[0].name)


def test_response_lists_genres_alphabetically_from_orm_links():
    links = [NS(genre=genre(2, 'romance')), NS(genre=genre(1, 'Fantasia'))]
    book = NS(id=1, title='T', author='A', is_active=True, isbn=None, genre=None, genres=links)
    assert [g.name for g in BookResponse.model_validate(book).genres] == ['Fantasia', 'romance']


def test_genre_text_with_genre_ids_is_rejected_with_stable_code_on_update():
    from app.core.exceptions import GenreTextWithGenreIdsError
    svc, repository = service()
    repository.employee_exists.return_value = True
    repository.get_with_copies.return_value = NS(id=1, is_active=True)
    with pytest.raises(GenreTextWithGenreIdsError) as error:
        svc.update_book(1, BookUpdate(genre='Texto', genre_ids=[1]), employee_id=9)
    assert (error.value.status_code, error.value.code) == (422, 'genre_text_with_genre_ids')
    repository.update_book.assert_not_called()


@pytest.mark.anyio
async def test_genre_text_with_genre_ids_is_rejected_on_create_before_any_lookup():
    from app.core.exceptions import GenreTextWithGenreIdsError
    svc, repository = service()
    repository.employee_exists.return_value = True
    with pytest.raises(GenreTextWithGenreIdsError):
        await svc.create_book(BookCreate(isbn='9788575225530', genre='x', genre_ids=[1], initial_copy=COPY), employee_id=9)
    repository.create_book.assert_not_called()


@pytest.fixture
def anyio_backend():
    return 'asyncio'


def test_foreign_key_violation_on_genre_is_404_not_500():
    from sqlalchemy.exc import IntegrityError
    from app.core.exceptions import GenreNotFoundError
    svc, repository = service([genre(1, 'Romance')])
    repository.employee_exists.return_value = True
    repository.get_with_copies.return_value = NS(id=1, is_active=True)
    orig = Exception('insert or update on table "book_genres" violates foreign key constraint "book_genres_genre_id_fkey"')
    repository.update_book.side_effect = IntegrityError('x', {}, orig)
    with pytest.raises(GenreNotFoundError) as error:
        svc.update_book(1, BookUpdate(genre_ids=[1]), employee_id=9)
    assert (error.value.status_code, error.value.code) == (404, 'genre_not_found')
