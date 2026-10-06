"""Inclusão de exemplar e inativação de obra (Issue #135) contra PostgreSQL descartável migrado pelo Alembic."""
from uuid import uuid4
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.models.domain import Book, Copy, DestinationType, Loan, LoanStatus
from app.repositories.book_repository import BookRepository
from app.repositories.copy_repository import CopyRepository
from app.schemas.book_schema import BookUpdate
from app.schemas.copy_schema import CopyCreate
from app.services.book_service import BookService
from app.services.copy_service import CopyService
from test_client_requests_postgres import records  # noqa: F401  (fixture)
from test_staff_desk_postgres import desk, didactic_copy  # noqa: F401  (fixtures)


def copy_service(db):
    return CopyService(CopyRepository(db), db)


def test_copy_creation_persists_and_duplicate_barcode_returns_409_without_new_row(desk):  # noqa: F811
    _, engine, book_id, _, seller_id = desk
    code = 'NEW-135-' + uuid4().hex[:12]
    with Session(engine) as db:
        created = copy_service(db).create_new_copy(
            CopyCreate(book_id=book_id, barcode=code, destination=DestinationType.DIDACTIC), actor_id=seller_id)
        assert (created.barcode, created.status.value, created.is_active) == (code, 'AVAILABLE', True)
    with Session(engine) as db:
        with pytest.raises(ApplicationError) as duplicate:
            copy_service(db).create_new_copy(
                CopyCreate(book_id=book_id, barcode=code, destination=DestinationType.DIDACTIC), actor_id=seller_id)
        assert duplicate.value.status_code == 409
        assert db.query(Copy).filter(Copy.barcode == code).count() == 1


def test_copy_creation_rejects_inactive_book_and_price_rules_are_validated(desk):  # noqa: F811
    _, engine, book_id, _, seller_id = desk
    for price in (None, 0):  # Issue #175: preço ausente ou zero é 422 de domínio, como na edição
        with Session(engine) as db:
            with pytest.raises(ApplicationError) as invalid:
                copy_service(db).create_new_copy(
                    CopyCreate(book_id=book_id, barcode='NEW-175-P', destination=DestinationType.COMMERCIAL,
                               sale_price=price), actor_id=seller_id)
            assert (invalid.value.status_code, invalid.value.code) == (422, 'copy_sale_price_required')
            assert db.query(Copy).filter(Copy.barcode == 'NEW-175-P').count() == 0
    with pytest.raises(ValueError):
        CopyCreate(book_id=book_id, barcode='X', destination=DestinationType.DIDACTIC, sale_price=10)
    with Session(engine) as db:
        db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(seller_id)})
        db.get(Book, book_id).is_active = False
        db.commit()
    with Session(engine) as db:
        with pytest.raises(ApplicationError) as inactive:
            copy_service(db).create_new_copy(
                CopyCreate(book_id=book_id, barcode='NEW-135-B', destination=DestinationType.DIDACTIC), actor_id=seller_id)
        assert inactive.value.status_code == 404


def test_book_inactivation_is_blocked_by_open_loan_and_keeps_everything(desk):  # noqa: F811
    """Regra aprovada (Issue #135): empréstimo OPEN de qualquer exemplar da obra bloqueia a inativação."""
    _, engine, book_id, client_id, seller_id = desk
    with Session(engine) as db:
        copy_id = didactic_copy(db, book_id).id
        now = datetime.now(timezone.utc)
        db.add(Loan(client_id=client_id, copy_id=copy_id, employee_id=seller_id, loan_date=now,
                    due_date=now + timedelta(days=30), status=LoanStatus.OPEN))
        db.commit()
    with Session(engine) as db:
        with pytest.raises(ApplicationError) as blocked:
            BookService(db=db, repository=BookRepository(db)).update_book(
                book_id, BookUpdate(is_active=False), employee_id=seller_id)
        assert (blocked.value.status_code, blocked.value.code) == (409, 'book_has_active_operations')
        assert blocked.value.details['counts'] == {'open_loans': 1, 'pending_loan_requests': 0, 'purchase_reservations': 0}
    with Session(engine) as db:
        assert db.get(Book, book_id).is_active is True
        assert db.get(Copy, copy_id).is_active is True
        assert db.query(Loan).filter(Loan.copy_id == copy_id, Loan.status == LoanStatus.OPEN).count() == 1
