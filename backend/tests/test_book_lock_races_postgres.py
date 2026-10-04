"""Corridas determinísticas sobre o lock do livro (Issue #135) contra PostgreSQL descartável.

Uma sessão "H" segura o lock da linha do livro numa transação aberta; a outra operação roda numa
thread e só é liberada depois de o PostgreSQL mostrar que ela está esperando por lock. O commit
de H define a ordem, então o resultado é determinístico em vez de depender de agendamento.
"""
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.models.domain import Book, Copy, Loan, LoanStatus
from app.repositories.book_repository import BookRepository
from app.repositories.client_pendency_repository import ClientPendencyRepository
from app.repositories.loan_repository import LoanRepository
from app.repositories.loan_request_repository import LoanRequestRepository
from app.repositories.purchase_request_repository import PurchaseRequestRepository
from app.repositories.sale_repository import SaleRepository
from app.schemas.book_schema import BookUpdate
from app.schemas.loan_request_schema import LoanRequestCreate
from app.schemas.loan_schema import LoanCreate
from app.schemas.purchase_request_schema import PurchaseRequestCreate
from app.schemas.sale_schema import SaleCreate
from app.services.book_service import BookService
from app.services.client_pendency_service import ClientPendencyService
from app.services.loan_request_service import LoanRequestService, business_today
from app.services.loan_service import LoanService
from app.services.purchase_request_service import PurchaseRequestService
from app.services.sale_service import SaleService
from test_client_requests_postgres import records  # noqa: F401  (fixture)
from test_copy_deletion_postgres import add_copy, api  # noqa: F401  (fixtures/helpers)
from test_copy_deletion_postgres import desk  # noqa: F401  (fixture usada por api)
from app.models.domain import DestinationType


def hold_book_lock(api):
    db = Session(api.engine)
    db.execute(select(Book).where(Book.id == api.book_id).with_for_update())
    db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(api.admin_id)})
    return db


def wait_until_blocked(engine, expected, timeout=15):
    deadline = time.monotonic() + timeout
    query = text("SELECT count(*) FROM pg_stat_activity "
                 "WHERE datname = current_database() AND wait_event_type = 'Lock'")
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            if conn.execute(query).scalar() >= expected:
                return
        time.sleep(0.05)
    raise AssertionError('a operação concorrente não ficou esperando pelo lock do livro')


def run_behind_lock(api, holder, *operations):
    """Dispara as operações, espera todas bloquearem no lock do livro e libera com commit de H."""
    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        futures = [pool.submit(operation) for operation in operations]
        try:
            wait_until_blocked(api.engine, len(operations))
        finally:
            holder.commit()
            holder.close()
        return [future.result(timeout=30) for future in futures]


def outcome(call):
    try:
        call()
        return 'ok'
    except ApplicationError as error:
        return error.code
    except Exception as error:  # HTTPException dos fluxos legados de empréstimo e venda
        return getattr(error, 'status_code', repr(error))


def deactivate_in(holder, api):
    holder.execute(text('UPDATE books SET is_active = false WHERE id = :id'), {'id': api.book_id})


def book_active(api):
    with Session(api.engine) as db:
        return db.get(Book, api.book_id).is_active


def delete_op(api, copy_id):
    def run():
        return outcome(lambda: api.service().delete_copy(copy_id, api.admin_id))
    return run


def loan_op(api, copy_id):
    def run():
        with Session(api.engine) as db:
            service = LoanService(LoanRepository(db), db, ClientPendencyService(db=db, repository=ClientPendencyRepository(db)))
            return outcome(lambda: service.create_loan(
                LoanCreate(client_id=api.client_id, copy_id=copy_id), employee_id=api.admin_id))
    return run


def sale_op(api, copy_id):
    def run():
        with Session(api.engine) as db:
            service = SaleService(SaleRepository(db), db)
            return outcome(lambda: service.create_sale(
                SaleCreate(client_id=api.client_id, items=[{'copy_id': copy_id, 'unit_price': '20.00'}]),
                employee_id=api.admin_id))
    return run


def inactivation_op(api):
    def run():
        with Session(api.engine) as db:
            def call():
                BookService(db=db, repository=BookRepository(db)).update_book(
                    api.book_id, BookUpdate(is_active=False), employee_id=api.admin_id)
            try:
                call()
                return 'ok'
            except ApplicationError as error:
                return (error.code, error.details['counts'] if error.details else None)
    return run


def test_two_deletes_of_the_same_copy_give_one_200_and_one_404(api):  # noqa: F811
    copy_id = add_copy(api)
    holder = hold_book_lock(api)
    results = run_behind_lock(api, holder, delete_op(api, copy_id), delete_op(api, copy_id))
    assert sorted(map(str, results)) == ['copy_not_found', 'ok']
    with Session(api.engine) as db:
        assert db.get(Copy, copy_id) is None


def test_delete_waits_for_an_uncommitted_loan_and_is_then_blocked(api):  # noqa: F811
    copy_id = add_copy(api)
    holder = hold_book_lock(api)
    now = datetime.now(timezone.utc)
    holder.add(Loan(client_id=api.client_id, copy_id=copy_id, employee_id=api.admin_id, loan_date=now,
                    due_date=now + timedelta(days=30), status=LoanStatus.OPEN))
    holder.flush()
    [result] = run_behind_lock(api, holder, delete_op(api, copy_id))
    assert result == 'copy_not_available'
    with Session(api.engine) as db:
        assert db.get(Copy, copy_id) is not None


def test_loan_waits_for_an_uncommitted_delete_and_then_finds_no_copy(api):  # noqa: F811
    copy_id = add_copy(api)
    holder = hold_book_lock(api)
    holder.execute(text('DELETE FROM copies WHERE id = :id'), {'id': copy_id})
    [result] = run_behind_lock(api, holder, loan_op(api, copy_id))
    assert result == 404
    with Session(api.engine) as db:
        assert db.query(Loan).filter(Loan.copy_id == copy_id).count() == 0


def test_loan_waits_for_inactivation_and_is_refused_with_book_inactive(api):  # noqa: F811
    copy_id = add_copy(api)
    holder = hold_book_lock(api)
    deactivate_in(holder, api)
    [result] = run_behind_lock(api, holder, loan_op(api, copy_id))
    assert result == 'book_inactive'
    assert not book_active(api)
    with Session(api.engine) as db:
        assert db.query(Loan).filter(Loan.copy_id == copy_id).count() == 0


def test_direct_sale_waits_for_inactivation_and_is_refused_with_book_inactive(api):  # noqa: F811
    copy_id = add_copy(api, DestinationType.COMMERCIAL)
    holder = hold_book_lock(api)
    deactivate_in(holder, api)
    [result] = run_behind_lock(api, holder, sale_op(api, copy_id))
    assert result == 'book_inactive'
    with Session(api.engine) as db:
        assert db.execute(text('SELECT count(*) FROM sale_items WHERE copy_id = :id'), {'id': copy_id}).scalar() == 0


def test_purchase_request_waits_for_inactivation_and_is_refused(api):  # noqa: F811
    holder = hold_book_lock(api)
    deactivate_in(holder, api)

    def request():
        with Session(api.engine) as db:
            return outcome(lambda: PurchaseRequestService(db, PurchaseRequestRepository(db)).create(
                PurchaseRequestCreate(book_id=api.book_id, pickup_date=business_today()), client_id=api.client_id))

    [result] = run_behind_lock(api, holder, request)
    assert result == 'book_not_found'


def test_pickup_request_waits_for_inactivation_and_is_refused(api):  # noqa: F811
    holder = hold_book_lock(api)
    deactivate_in(holder, api)

    def request():
        with Session(api.engine) as db:
            return outcome(lambda: LoanRequestService(db, LoanRequestRepository(db)).create(
                LoanRequestCreate(book_id=api.book_id, pickup_date=business_today()), client_id=api.client_id))

    [result] = run_behind_lock(api, holder, request)
    assert result == 'book_not_found'


def test_inactivation_waits_for_an_uncommitted_direct_loan_and_is_then_blocked(api):  # noqa: F811
    copy_id = add_copy(api)
    holder = hold_book_lock(api)
    now = datetime.now(timezone.utc)
    holder.add(Loan(client_id=api.client_id, copy_id=copy_id, employee_id=api.admin_id, loan_date=now,
                    due_date=now + timedelta(days=30), status=LoanStatus.OPEN))
    holder.flush()
    [result] = run_behind_lock(api, holder, inactivation_op(api))
    assert result[0] == 'book_has_active_operations'
    assert result[1]['open_loans'] == 1
    assert book_active(api)


def test_inactivation_waits_for_an_uncommitted_pickup_request_and_is_then_blocked(api):  # noqa: F811
    holder = hold_book_lock(api)
    holder.execute(text(
        "INSERT INTO loan_requests (book_id, client_id, pickup_date, due_date) "
        "VALUES (:b, :c, :d, (CAST(:d AS date) + interval '1 month')::date)"),
        {'b': api.book_id, 'c': api.client_id, 'd': business_today()})
    [result] = run_behind_lock(api, holder, inactivation_op(api))
    assert result[0] == 'book_has_active_operations'
    assert result[1]['pending_loan_requests'] == 1
    assert book_active(api)
