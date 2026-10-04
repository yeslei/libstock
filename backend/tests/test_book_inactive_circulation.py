"""Empréstimo e venda diretos recusam obra inativa (Issue #135): book_inactive, com lock do livro antes do exemplar."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import BookInactiveError
from app.models.domain import CopyStatus, DestinationType
from app.schemas.loan_schema import LoanCreate
from app.schemas.sale_schema import SaleCreate
from app.services.loan_service import LoanService
from app.services.sale_service import SaleService


def a_copy():
    return SimpleNamespace(id=15, book_id=1, is_active=True, status=CopyStatus.AVAILABLE,
                           destination=DestinationType.COMMERCIAL)


def test_emprestimo_em_obra_inativa_retorna_409_book_inactive_sem_gravar():
    repository, db = MagicMock(), MagicMock()
    repository.lock_book_for_copy.return_value = SimpleNamespace(id=1, is_active=False)
    repository.find_copy_for_loan.return_value = a_copy()
    service = LoanService(repository=repository, db=db, client_pendency_service=MagicMock())
    with pytest.raises(BookInactiveError) as error:
        service.create_loan(LoanCreate(client_id=42, copy_id=15), employee_id=7)
    assert (error.value.status_code, error.value.code) == (409, "book_inactive")
    repository.create_loan.assert_not_called()
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_emprestimo_trava_o_livro_antes_do_exemplar():
    repository = MagicMock()
    repository.lock_book_for_copy.return_value = SimpleNamespace(id=1, is_active=False)
    repository.find_copy_for_loan.return_value = a_copy()
    service = LoanService(repository=repository, db=MagicMock(), client_pendency_service=MagicMock())
    with pytest.raises(BookInactiveError):
        service.create_loan(LoanCreate(client_id=42, copy_id=15), employee_id=7)
    names = [call[0] for call in repository.method_calls]
    assert names.index("lock_book_for_copy") < names.index("find_copy_for_loan")


def test_venda_em_obra_inativa_retorna_409_book_inactive_sem_gravar():
    repository, db = MagicMock(), MagicMock()
    repository.find_client.return_value = SimpleNamespace(id=42)
    repository.lock_books_for_copies.return_value = {1: SimpleNamespace(id=1, is_active=False)}
    repository.find_copies_for_sale.return_value = [a_copy()]
    data = SaleCreate(client_id=42, items=[{"copy_id": 15, "unit_price": Decimal("10.00")}])
    with pytest.raises(BookInactiveError) as error:
        SaleService(repository, db).create_sale(data, employee_id=7)
    assert (error.value.status_code, error.value.code) == (409, "book_inactive")
    repository.create_sale.assert_not_called()
    db.rollback.assert_called_once()
    names = [call[0] for call in repository.method_calls]
    assert names.index("lock_books_for_copies") < names.index("find_copies_for_sale")
