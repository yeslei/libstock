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
