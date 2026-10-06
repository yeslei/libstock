"""Comprovantes (Issue #152): contratos HTTP e regras do service sem banco."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace as NS
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.controllers.receipt_controller import get_receipt_service
from app.core.exceptions import ApplicationError
from app.dependencies.authentication import get_current_user
from app.main import app
from app.models.domain import LoanStatus, SaleStatus
from app.schemas.receipt_schema import LoanReceipt, ReceiptBook, ReceiptPerson
from app.services.receipt_service import ReceiptService

http = TestClient(app)
SP = ZoneInfo("America/Sao_Paulo")
START = datetime(2026, 3, 1, 10, tzinfo=SP)
DUE = datetime(2026, 4, 1, 10, tzinfo=SP)


@pytest.fixture(autouse=True)
def _reset():
    yield
    app.dependency_overrides.clear()


def loan_row(*, status=LoanStatus.OPEN, client_id=7, returned_at=None):
    loan = NS(id=11, client_id=client_id, employee_id=3, loan_date=START, due_date=DUE,
              status=status, returned_at=returned_at)
    return (loan, NS(id=5, barcode="COD-5"), NS(title="Dom Casmurro", author="Machado", isbn="9788535902778"),
            "Ana Cliente", "MAT-1", "Beto Balcão", "FUNC-9")


def service_with(repository, role="SELLER", user_id=3):
    return ReceiptService(Mock(), repository), NS(id=user_id, role_codes=[role])


def repo(row=None, active=True):
    repository = Mock()
    repository.find_loan.return_value = row
    repository.is_active_employee.return_value = active
    return repository


def test_loan_receipt_maps_persisted_fields():
    service, staff = service_with(repo(loan_row()))
    receipt = service.loan_receipt(11, staff)
    assert receipt.number == 11 and receipt.copy_barcode == "COD-5" and receipt.copy_id == 5
    assert receipt.client == ReceiptPerson(id=7, name="Ana Cliente", code="MAT-1")
    assert receipt.employee == ReceiptPerson(id=3, name="Beto Balcão", code="FUNC-9")
    assert receipt.book == ReceiptBook(title="Dom Casmurro", author="Machado", isbn="9788535902778")
    assert (receipt.loan_date, receipt.due_date) == (START, DUE)


def test_return_receipt_requires_returned_loan():
    service, staff = service_with(repo(loan_row()))
    with pytest.raises(ApplicationError) as error:
        service.return_receipt(11, staff)
    assert (error.value.status_code, error.value.code) == (409, "loan_not_returned")


@pytest.mark.parametrize("returned,late", [
    (datetime(2026, 3, 30, 9, tzinfo=SP), 0),
    (datetime(2026, 4, 1, 23, 59, tzinfo=SP), 0),  # vencer hoje não é atraso
    (datetime(2026, 4, 2, 0, 1, tzinfo=SP), 1),
    (datetime(2026, 4, 11, 8, tzinfo=SP), 10),
    (datetime(2026, 4, 2, 2, 30, tzinfo=timezone.utc), 0),  # 23h30 do dia 1 em São Paulo
])
def test_return_receipt_late_days_follow_business_calendar(returned, late):
    row = loan_row(status=LoanStatus.RETURNED, returned_at=returned)
    service, staff = service_with(repo(row))
    receipt = service.return_receipt(11, staff)
    assert receipt.days_late == late and receipt.returned_at == returned


def test_missing_and_cancelled_loans_are_404():
    for row in (None, loan_row(status=LoanStatus.CANCELLED)):
        service, staff = service_with(repo(row))
        for operation in (service.loan_receipt, service.return_receipt):
            with pytest.raises(ApplicationError) as error:
                operation(11, staff)
            assert (error.value.status_code, error.value.code) == (404, "receipt_not_found")


def test_client_ownership_hides_foreign_loans_and_never_asks_for_employee():
    repository = repo(loan_row(status=LoanStatus.RETURNED, returned_at=DUE, client_id=7))
    service, owner = service_with(repository, role="USER", user_id=7)
    assert service.loan_receipt(11, owner).number == 11
    assert service.return_receipt(11, owner).days_late == 0
    stranger = NS(id=8, role_codes=["USER"])
    for operation in (service.loan_receipt, service.return_receipt):
        with pytest.raises(ApplicationError) as error:
            operation(11, stranger)
        assert (error.value.status_code, error.value.code) == (404, "receipt_not_found")
    repository.is_active_employee.assert_not_called()


def test_inactive_employee_is_blocked_even_with_staff_role():
    service, staff = service_with(repo(loan_row(), active=False), role="ADMINISTRATOR")
    with pytest.raises(ApplicationError) as error:
        service.loan_receipt(11, staff)
    assert (error.value.status_code, error.value.code) == (403, "employee_record_required")


def test_database_failure_becomes_stable_500_and_rolls_back():
    repository = repo()
    repository.find_loan.side_effect = SQLAlchemyError("boom")
    service, staff = service_with(repository)
    with pytest.raises(ApplicationError) as error:
        service.loan_receipt(11, staff)
    assert (error.value.status_code, error.value.code) == (500, "receipt_query_error")
    service.db.rollback.assert_called_once()


def sale(status=SaleStatus.CONFIRMED, client_id=7):
    return NS(id=21, client_id=client_id, employee_id=3, status=status, total_amount=Decimal("49.75"),
              sale_date=START)


def sale_repo(sale_row):
    repository = Mock()
    repository.is_active_employee.return_value = True
    repository.find_sale.return_value = sale_row
    repository.sale_parties.return_value = (NS(name="Beto Balcão", employee_code="FUNC-9"), "Ana Cliente")
    book = NS(title="Dom Casmurro", author="Machado", isbn=None)
    repository.sale_items.return_value = [
        (NS(unit_price=Decimal("37.50")), NS(id=1, barcode="A"), book),
        (NS(unit_price=Decimal("12.25")), NS(id=2, barcode="B"), book),
    ]
    return repository


def test_sale_receipt_lists_items_and_total():
    service, staff = service_with(sale_repo(sale()))
    receipt = service.sale_receipt(21, staff)
    assert receipt.number == 21 and receipt.total_amount == Decimal("49.75")
    assert [(i.copy_barcode, i.unit_price) for i in receipt.items] == [("A", Decimal("37.50")), ("B", Decimal("12.25"))]
    assert receipt.client == ReceiptPerson(id=7, name="Ana Cliente") and receipt.employee.code == "FUNC-9"


def test_sale_without_client_has_null_client_and_is_hidden_from_users():
    repository = sale_repo(sale(client_id=None))
    service, staff = service_with(repository)
    assert service.sale_receipt(21, staff).client is None
    with pytest.raises(ApplicationError) as error:
        service.sale_receipt(21, NS(id=7, role_codes=["USER"]))
    assert error.value.status_code == 404


@pytest.mark.parametrize("sale_row", [None, sale(SaleStatus.PENDING), sale(SaleStatus.CANCELLED)])
def test_only_confirmed_sales_have_receipt(sale_row):
    service, staff = service_with(sale_repo(sale_row))
    with pytest.raises(ApplicationError) as error:
        service.sale_receipt(21, staff)
    assert (error.value.status_code, error.value.code) == (404, "receipt_not_found")


PATHS = ["loans/1", "returns/1", "sales/1"]


@pytest.mark.parametrize("path", PATHS)
def test_routes_require_session_and_allowed_role(path):
    fake = Mock()
    app.dependency_overrides[get_receipt_service] = lambda: fake
    assert http.get(f"/api/v1/receipts/{path}").status_code == 401
    app.dependency_overrides[get_current_user] = lambda: NS(id=3, role_codes=["STOCK_KEEPER"])
    assert http.get(f"/api/v1/receipts/{path}").status_code == 403
    assert not fake.method_calls


@pytest.mark.parametrize("path", [p.replace("1", bad) for p in PATHS for bad in ("0", "-1", "x")])
def test_routes_validate_identifier(path):
    app.dependency_overrides[get_receipt_service] = lambda: Mock()
    app.dependency_overrides[get_current_user] = lambda: NS(id=3, role_codes=["SELLER"])
    assert http.get(f"/api/v1/receipts/{path}").status_code == 422


def test_route_passes_authenticated_user_and_serializes_response():
    receipt = LoanReceipt(number=11, client=ReceiptPerson(id=7, name="Ana"), employee=ReceiptPerson(id=3, name="Beto"),
                          book=ReceiptBook(title="T", author="A"), copy_id=5, copy_barcode="C",
                          loan_date=START, due_date=START + timedelta(days=30))
    fake = Mock()
    fake.loan_receipt.return_value = receipt
    app.dependency_overrides[get_receipt_service] = lambda: fake
    user = NS(id=7, role_codes=["USER"])
    app.dependency_overrides[get_current_user] = lambda: user
    response = http.get("/api/v1/receipts/loans/11?client_id=99")
    assert response.status_code == 200 and response.json()["number"] == 11
    fake.loan_receipt.assert_called_once_with(11, user)
