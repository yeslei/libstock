"""Leitura da auditoria (Issue #49): autorização, filtros, paginação e erros estáveis."""

from datetime import date, datetime, timezone
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import ApplicationError
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_audit_log_service
from app.main import app
from app.schemas.audit_log_schema import AuditLogPage
from app.services.audit_log_service import AuditLogService


BASE = "/api/v1/audit-logs"


def audit_entry(**overrides):
    values = dict(
        id=1,
        occurred_at=datetime(2026, 11, 10, 12, tzinfo=timezone.utc),
        employee_id=4,
        entity_type="copies",
        entity_id="10",
        operation="UPDATE",
        old_value={"status": "BORROWED"},
        new_value={"status": "AVAILABLE"},
    )
    values.update(overrides)
    return NS(**values)


@pytest.fixture
def http():
    app.dependency_overrides.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_administrator_reads_audit_logs(http):
    page = AuditLogPage(
        items=[{
            "id": 1,
            "occurred_at": datetime(2026, 11, 10, 12, tzinfo=timezone.utc),
            "employee_id": 4,
            "employee_name": "Ana",
            "entity_type": "copies",
            "entity_id": "10",
            "operation": "UPDATE",
            "old_value": {"status": "BORROWED"},
            "new_value": {"status": "AVAILABLE"},
        }],
        total=1,
        limit=50,
        offset=0,
    )
    service = Mock()
    service.list_logs.return_value = page
    app.dependency_overrides[get_audit_log_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: NS(id=1, role_codes=["ADMINISTRATOR"])

    response = http.get(BASE)

    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["limit"], body["offset"]) == (1, 50, 0)
    assert body["items"][0]["employee_name"] == "Ana"
    assert body["items"][0]["new_value"] == {"status": "AVAILABLE"}


@pytest.mark.parametrize("role", ["SELLER", "STOCK_KEEPER", "USER"])
def test_non_administrator_roles_are_forbidden(http, role):
    app.dependency_overrides[get_current_user] = lambda: NS(id=2, role_codes=[role])

    response = http.get(BASE)

    assert (response.status_code, response.json()["code"]) == (403, "permission_denied")


def test_missing_session_is_unauthorized(http):
    response = http.get(BASE)

    assert (response.status_code, response.json()["code"]) == (401, "invalid_token")


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_audit_logs_have_no_write_endpoint(http, method):
    app.dependency_overrides[get_current_user] = lambda: NS(id=1, role_codes=["ADMINISTRATOR"])

    response = http.request(method, BASE)

    assert response.status_code == 405


def test_filters_and_pagination_are_forwarded_to_the_service(http):
    service = Mock()
    service.list_logs.return_value = AuditLogPage(items=[], total=0, limit=25, offset=50)
    app.dependency_overrides[get_audit_log_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: NS(id=1, role_codes=["ADMINISTRATOR"])

    response = http.get(BASE, params={
        "entity_type": "copies",
        "entity_id": "10",
        "operation": "UPDATE",
        "employee_id": 4,
        "date_from": "2026-11-01",
        "date_to": "2026-11-10",
        "limit": 25,
        "offset": 50,
    })

    assert response.status_code == 200
    service.list_logs.assert_called_once_with(
        entity_type="copies",
        entity_id="10",
        operation="UPDATE",
        employee_id=4,
        date_from=date(2026, 11, 1),
        date_to=date(2026, 11, 10),
        limit=25,
        offset=50,
    )


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"employee_id": 0}])
def test_invalid_query_is_rejected_before_the_service(http, params):
    service = Mock()
    app.dependency_overrides[get_audit_log_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: NS(id=1, role_codes=["ADMINISTRATOR"])

    response = http.get(BASE, params=params)

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")
    service.list_logs.assert_not_called()


def test_service_maps_employee_name_and_pagination():
    repository = Mock()
    repository.list_entries.return_value = (
        [(audit_entry(), "Ana"), (audit_entry(id=2, employee_id=None), None)],
        7,
    )
    service = AuditLogService(Mock(), repository)

    page = service.list_logs(limit=2, offset=4)

    assert (page.total, page.limit, page.offset) == (7, 2, 4)
    assert [item.employee_name for item in page.items] == ["Ana", None]
    repository.list_entries.assert_called_once_with(
        entity_type=None,
        entity_id=None,
        operation=None,
        employee_id=None,
        date_from=None,
        date_to=None,
        limit=2,
        offset=4,
    )


def test_service_normalizes_blank_filters():
    repository = Mock()
    repository.list_entries.return_value = ([], 0)
    service = AuditLogService(Mock(), repository)

    service.list_logs(entity_type="  books ", entity_id="   ", operation="")

    assert repository.list_entries.call_args.kwargs["entity_type"] == "books"
    assert repository.list_entries.call_args.kwargs["entity_id"] is None
    assert repository.list_entries.call_args.kwargs["operation"] is None


@pytest.mark.parametrize(
    "kwargs,code",
    [
        ({"limit": 0}, "invalid_pagination"),
        ({"limit": 101}, "invalid_pagination"),
        ({"offset": -1}, "invalid_pagination"),
        ({"date_from": date(2026, 11, 10), "date_to": date(2026, 11, 1)}, "invalid_date_range"),
    ],
)
def test_service_rejects_invalid_parameters(kwargs, code):
    service = AuditLogService(Mock(), Mock())

    with pytest.raises(ApplicationError) as error:
        service.list_logs(**kwargs)

    assert (error.value.status_code, error.value.code) == (422, code)


def test_repository_failure_becomes_stable_error():
    db = Mock()
    repository = Mock()
    repository.list_entries.side_effect = SQLAlchemyError("failure")
    service = AuditLogService(db, repository)

    with pytest.raises(ApplicationError) as error:
        service.list_logs()

    assert (error.value.status_code, error.value.code) == (500, "audit_log_query_error")
    db.rollback.assert_called_once()
