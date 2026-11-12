"""Leitura e imutabilidade dos logs de auditoria (Issue #49) em PostgreSQL descartável.

Depende de `LIBSTOCK_V2_TEST_DATABASE_URL` migrado pelo Alembic; sem a variável,
os testes são pulados (ver test_client_requests_postgres).
"""

from datetime import datetime, timezone
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.dependencies.authentication import get_current_user
from app.main import app
from app.models.domain import AuditLog, Employee, Profile, Role, UserRole
from app.models.user import User
from test_client_requests_postgres import records  # noqa: F401  (fixture)


BASE = "/api/v1/audit-logs"


@pytest.fixture
def audit(records):  # noqa: F811
    engine, _book_id, _client_id = records
    with Session(engine) as db:
        role = db.scalar(select(Role).where(Role.code == "ADMINISTRATOR"))
        admin = User(name="Admin Auditoria", email=f"{uuid4().hex}@test.invalid", password_hash="test")
        db.add(admin)
        db.flush()
        db.add(Profile(id=admin.id))
        db.flush()
        db.add(Employee(id=admin.id, role_id=role.id, employee_code=uuid4().hex))
        db.add(UserRole(user_id=admin.id, role_id=role.id))
        db.flush()
        entries = [
            AuditLog(
                employee_id=admin.id,
                entity_type="copies",
                entity_id="10",
                operation="UPDATE",
                old_value={"status": "BORROWED"},
                new_value={"status": "AVAILABLE"},
                occurred_at=datetime(2026, 11, 10, 12, tzinfo=timezone.utc),
            ),
            AuditLog(
                employee_id=None,
                entity_type="purchase_reservations",
                entity_id="20",
                operation="CANCEL",
                new_value={"reason": "desistência"},
                occurred_at=datetime(2026, 11, 11, 12, tzinfo=timezone.utc),
            ),
            AuditLog(
                employee_id=admin.id,
                entity_type="books",
                entity_id="30",
                operation="INSERT",
                new_value={"title": "Livro"},
                occurred_at=datetime(2026, 11, 12, 12, tzinfo=timezone.utc),
            ),
        ]
        db.add_all(entries)
        db.commit()
        admin_id = admin.id
        entry_ids = [entry.id for entry in entries]

    app.dependency_overrides[get_current_user] = lambda: NS(id=admin_id, role_codes=["ADMINISTRATOR"])
    yield TestClient(app), engine, admin_id, entry_ids
    app.dependency_overrides.clear()


def test_lists_newest_first_with_employee_name(audit):  # noqa: F811
    http, _engine, _admin_id, _entry_ids = audit

    response = http.get(BASE)

    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["limit"], body["offset"]) == (3, 50, 0)
    assert [item["operation"] for item in body["items"]] == ["INSERT", "CANCEL", "UPDATE"]
    assert body["items"][0]["employee_name"] == "Admin Auditoria"
    assert body["items"][1]["employee_name"] is None
    assert body["items"][2]["old_value"] == {"status": "BORROWED"}


@pytest.mark.parametrize(
    "params,total",
    [
        ({"entity_type": "copies"}, 1),
        ({"operation": "CANCEL"}, 1),
        ({"entity_id": "20"}, 1),
        ({"entity_type": "copies", "entity_id": "20"}, 0),
        ({"date_from": "2026-11-12", "date_to": "2026-11-12"}, 1),
        ({"date_from": "2026-11-11"}, 2),
        ({"date_to": "2026-11-10"}, 1),
    ],
)
def test_filters_narrow_the_result(audit, params, total):  # noqa: F811
    http, _engine, _admin_id, _entry_ids = audit

    body = http.get(BASE, params=params).json()

    assert body["total"] == total
    assert len(body["items"]) == total


def test_employee_filter_matches_the_actor(audit):  # noqa: F811
    http, _engine, admin_id, _entry_ids = audit

    body = http.get(BASE, params={"employee_id": admin_id}).json()

    assert body["total"] == 2
    assert {item["employee_name"] for item in body["items"]} == {"Admin Auditoria"}


def test_pagination_is_stable_and_deterministic(audit):  # noqa: F811
    http, _engine, _admin_id, _entry_ids = audit

    first = http.get(BASE, params={"limit": 2, "offset": 0}).json()
    second = http.get(BASE, params={"limit": 2, "offset": 2}).json()

    assert [item["operation"] for item in first["items"]] == ["INSERT", "CANCEL"]
    assert [item["operation"] for item in second["items"]] == ["UPDATE"]
    assert (first["total"], second["total"]) == (3, 3)


def test_inverted_date_range_returns_stable_error(audit):  # noqa: F811
    http, _engine, _admin_id, _entry_ids = audit

    response = http.get(BASE, params={"date_from": "2026-11-12", "date_to": "2026-11-10"})

    assert (response.status_code, response.json()["code"]) == (422, "invalid_date_range")


def test_audit_logs_cannot_be_updated_or_deleted(audit):  # noqa: F811
    _http, engine, _admin_id, entry_ids = audit
    entry_id = entry_ids[0]

    for statement in (
        "UPDATE audit_logs SET operation = 'ALTERADO' WHERE id = :id",
        "DELETE FROM audit_logs WHERE id = :id",
    ):
        with engine.connect() as connection:
            with pytest.raises(DBAPIError) as error:
                connection.execute(text(statement), {"id": entry_id})
            connection.rollback()
        assert "cannot be modified or deleted" in str(error.value)

    with engine.connect() as connection:
        assert connection.scalar(
            text("SELECT operation FROM audit_logs WHERE id = :id"), {"id": entry_id}
        ) == "UPDATE"
        assert connection.scalar(
            text("SELECT count(*) FROM audit_logs WHERE id = :id"), {"id": entry_id}
        ) == 1
