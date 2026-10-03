"""Consultas de acervo do balcão contra PostgreSQL descartável migrado pelo Alembic (ver test_staff_desk_postgres)."""
from datetime import datetime, timedelta, timezone
from random import randint
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.domain import (
    Book, Copy, CopyStatus, DestinationType, Loan, LoanStatus, Profile, Sale, SaleItem, SaleStatus,
)
from test_client_requests_postgres import records  # noqa: F401  (fixture)
from test_staff_desk_postgres import BASE, commercial_copy, desk, didactic_copy  # noqa: F401  (fixtures)


def as_employee(db, employee_id):
    """Alterações de acervo exigem o funcionário responsável na transação (auditoria por trigger)."""
    db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(employee_id)})


def tag_book(engine, book_id, employee_id):
    """Dá ao livro de teste um ISBN compacto único e devolve (isbn, título)."""
    isbn = '978' + ''.join(str(randint(0, 9)) for _ in range(10))
    with Session(engine) as db:
        as_employee(db, employee_id)
        book = db.get(Book, book_id)
        book.isbn = isbn
        book.genre = 'Romance'
        book.title = f'Livro {uuid4().hex[:12]}'
        book.author = f'Autor {uuid4().hex[:12]}'
        db.commit()
        return isbn, book.title, book.author


def test_catalog_list_counts_and_searches_by_title_author_and_isbn(desk):  # noqa: F811
    http, engine, book_id, _, seller_id = desk
    isbn, title, author = tag_book(engine, book_id, seller_id)
    for term in (title, author, isbn, f'{isbn[:3]}-{isbn[3:]}', title.upper()):
        found = http.get(f'{BASE}/books', params={'q': term}).json()
        assert [b['id'] for b in found] == [book_id], term
    book = found[0]
    assert set(book) == {'id', 'title', 'author', 'isbn', 'genre', 'is_active', 'total_copies', 'didactic_copies',
                         'commercial_copies'}
    assert (book['total_copies'], book['didactic_copies'], book['commercial_copies'], book['genre']) == (2, 1, 1, 'Romance')
    assert http.get(f'{BASE}/books', params={'q': '%%'}).json() == []  # curinga é literal
    assert http.get(f'{BASE}/books', params={'q': 'inexistente-xyz'}).json() == []
    assert len(http.get(f'{BASE}/books', params={'limit': 1}).json()) == 1


def test_catalog_counts_ignore_sold_and_inactive_copies_but_keep_inactive_books(desk):  # noqa: F811
    http, engine, book_id, _, seller_id = desk
    _, title, _ = tag_book(engine, book_id, seller_id)
    with Session(engine) as db:
        as_employee(db, seller_id)
        sold = Copy(book_id=book_id, barcode='SOLD-' + str(randint(10**8, 10**9)),
                    destination=DestinationType.COMMERCIAL, sale_price=9)
        db.add_all([Copy(book_id=book_id, barcode='INA-' + str(randint(10**8, 10**9)),
                         destination=DestinationType.DIDACTIC, is_active=False), sold])
        sale = Sale(employee_id=seller_id, total_amount=9, status=SaleStatus.PENDING)
        db.add(sale); db.flush()
        db.add(SaleItem(sale_id=sale.id, copy_id=sold.id, unit_price=9)); db.flush()
        sale.status = SaleStatus.CONFIRMED; db.flush()
        sold.status = CopyStatus.SOLD
        db.get(Book, book_id).is_active = False
        db.commit()
    book = http.get(f'{BASE}/books', params={'q': title}).json()[0]
    assert book['id'] == book_id
    assert (book['is_active'], book['total_copies'], book['didactic_copies'], book['commercial_copies']) == (False, 2, 1, 1)


def test_catalog_detail_flags_free_pending_sale_and_unknown_book(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    with Session(engine) as db:
        commercial_id = commercial_copy(db, book_id).id
        didactic_id = didactic_copy(db, book_id).id
    detail = http.get(f'{BASE}/books/{book_id}').json()
    flags = {c['id']: (c['free'], c['allocated_for_purchase']) for c in detail['copies']}
    assert flags == {commercial_id: (True, False), didactic_id: (True, False)}
    assert detail['total_copies'] == 2 and 'sale_price' in detail['copies'][0]

    with Session(engine) as db:  # venda pendente: o exemplar deixa de ser livre, sem mudar de status
        sale = Sale(employee_id=seller_id, total_amount=25, status=SaleStatus.PENDING)
        db.add(sale); db.flush()
        db.add(SaleItem(sale_id=sale.id, copy_id=commercial_id, unit_price=25))
        db.commit()
    detail = http.get(f'{BASE}/books/{book_id}').json()
    assert {c['id']: c['free'] for c in detail['copies']}[commercial_id] is False

    missing = http.get(f'{BASE}/books/999999999')
    assert (missing.status_code, missing.json()['code']) == (404, 'book_not_found')


def test_copy_lookup_by_barcode_isbn_and_title_with_sale_decision(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    isbn, title, author = tag_book(engine, book_id, seller_id)
    with Session(engine) as db:
        commercial = commercial_copy(db, book_id)
        didactic = didactic_copy(db, book_id)
        commercial_id, commercial_code, didactic_code = commercial.id, commercial.barcode, didactic.barcode

    by_code = http.get(f'{BASE}/copies', params={'q': commercial_code}).json()
    assert [c['id'] for c in by_code] == [commercial_id]
    item = by_code[0]
    assert (item['sellable'], item['sale_block_reason'], item['free'], item['free_commercial_copies']) == (True, None, True, 1)
    assert item['book']['id'] == book_id and item['book']['isbn'] == isbn and float(item['sale_price']) == 25.0

    by_isbn = http.get(f'{BASE}/copies', params={'q': f'{isbn[:3]}-{isbn[3:]}'}).json()
    assert {c['barcode'] for c in by_isbn} == {commercial_code, didactic_code}
    by_title = {c['barcode']: c for c in http.get(f'{BASE}/copies', params={'q': title}).json()}
    assert by_title[didactic_code]['sellable'] is False and by_title[didactic_code]['sale_block_reason'] == 'DIDACTIC'

    with Session(engine) as db:
        sale = Sale(employee_id=seller_id, total_amount=25, status=SaleStatus.PENDING)
        db.add(sale); db.flush()
        db.add(SaleItem(sale_id=sale.id, copy_id=commercial_id, unit_price=25))
        db.commit()
    blocked = http.get(f'{BASE}/copies', params={'q': commercial_code}).json()[0]
    assert (blocked['sellable'], blocked['sale_block_reason'], blocked['free_commercial_copies']) == (False, 'NOT_AVAILABLE', 0)
    assert http.get(f'{BASE}/copies', params={'q': '%'}).json() == []


def test_copy_lookup_omits_inactive_copies_and_requires_term(desk):  # noqa: F811
    http, engine, book_id, _, seller_id = desk
    with Session(engine) as db:
        as_employee(db, seller_id)
        code = 'OFF-' + str(randint(10**8, 10**9))
        db.add(Copy(book_id=book_id, barcode=code, destination=DestinationType.DIDACTIC, is_active=False))
        db.commit()
    assert http.get(f'{BASE}/copies', params={'q': code}).json() == []
    assert http.get(f'{BASE}/copies', params={'q': '   '}).status_code == 422


def test_open_loans_can_be_found_by_isbn_for_returns(desk):  # noqa: F811
    http, engine, book_id, client_id, seller_id = desk
    isbn, *_ = tag_book(engine, book_id, seller_id)
    with Session(engine) as db:
        copy_id = didactic_copy(db, book_id).id
        now = datetime.now(timezone.utc)
        db.add(Loan(client_id=client_id, copy_id=copy_id, employee_id=seller_id, loan_date=now,
                    due_date=now + timedelta(days=30), status=LoanStatus.OPEN))
        db.commit()
    assert [loan['copy_id'] for loan in http.get(f'{BASE}/loans', params={'q': isbn}).json()] == [copy_id]
    hyphenated = http.get(f'{BASE}/loans', params={'q': f'{isbn[:3]}-{isbn[3:]}', 'client_id': client_id}).json()
    assert [loan['copy_id'] for loan in hyphenated] == [copy_id]
    assert http.get(f'{BASE}/loans', params={'q': '9780000000000x', 'client_id': client_id}).json() == []


def test_inactive_employee_cannot_read_catalog(desk):  # noqa: F811
    http, engine, book_id, _, seller_id = desk
    with Session(engine) as db:
        db.get(Profile, seller_id).is_active = False
        db.commit()
    for path in ('/books', f'/books/{book_id}', '/copies?q=abc'):
        response = http.get(BASE + path)
        assert (response.status_code, response.json()['code']) == (403, 'employee_record_required')
