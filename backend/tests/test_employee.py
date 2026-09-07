from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    DuplicateEmailError,
    DuplicateEmployeeCodeError,
    InactiveUserError,
    PersistenceError,
)
from app.dependencies.authentication import get_current_user
from app.main import app
from app.repositories.employee_repository import EmployeeCreated, EmployeeRepository
from app.schemas.employee_schema import EmployeeCreate


VALID_PAYLOAD = {
    "name": "Ana Souza",
    "email": "ana@example.com",
    "password": "senhasegura",
    "accessLevel": "MANAGER",
}


def make_user(role_codes: list[str]) -> MagicMock:
    user = MagicMock()
    user.role_codes = role_codes
    return user


def make_created(role_code: str = "MANAGER") -> EmployeeCreated:
    return EmployeeCreated(id=42, name="Ana Souza", email="ana@example.com", role_code=role_code)


@pytest.fixture
def admin_client() -> TestClient:
    from app.controllers.employee_controller import get_employee_service

    service = MagicMock()
    service.register.return_value = make_created()
    app.dependency_overrides[get_current_user] = lambda: make_user(["ADMINISTRATOR"])
    app.dependency_overrides[get_employee_service] = lambda: service
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_employee_service, None)


def test_no_token_returns_401():
    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/employees/", json=VALID_PAYLOAD
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


def test_manager_cannot_create_employee():
    app.dependency_overrides[get_current_user] = lambda: make_user(["MANAGER"])
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/v1/employees/", json=VALID_PAYLOAD
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_inactive_user_cannot_create_employee():
    app.dependency_overrides[get_current_user] = lambda: (_ for _ in ()).throw(InactiveUserError())
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/v1/employees/", json=VALID_PAYLOAD
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403
    assert response.json()["code"] == "inactive_user"


def test_canonical_role_is_accepted(admin_client):
    response = admin_client.post("/api/v1/employees/", json=VALID_PAYLOAD)
    assert response.status_code == 201


@pytest.mark.parametrize("role", ["ATENDENTE", "VENDEDOR", "ESTOQUISTA", "GERENTE"])
def test_portuguese_alias_is_rejected(admin_client, role):
    response = admin_client.post(
        "/api/v1/employees/", json={**VALID_PAYLOAD, "accessLevel": role}
    )
    assert response.status_code == 422


def test_administrator_role_is_rejected_in_payload(admin_client):
    response = admin_client.post(
        "/api/v1/employees/", json={**VALID_PAYLOAD, "accessLevel": "ADMINISTRATOR"}
    )
    assert response.status_code == 422


def test_response_returns_persisted_role_and_excludes_password(admin_client):
    from app.controllers.employee_controller import get_employee_service

    service = app.dependency_overrides[get_employee_service]()
    service.register.return_value = make_created("SELLER")
    response = admin_client.post("/api/v1/employees/", json=VALID_PAYLOAD)
    body = response.json()
    assert body["role_code"] == "SELLER"
    assert "password" not in body
    assert "password_hash" not in body


def test_repository_persists_profile_before_employee():
    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(id=1, code="MANAGER")

    def assign_user_id_after_user_flush():
        if db.flush.call_count == 1:
            db.add.call_args_list[0].args[0].id = 7

    db.flush.side_effect = assign_user_id_after_user_flush
    payload = EmployeeCreate(**VALID_PAYLOAD)

    result = EmployeeRepository(db).create(payload)

    assert result.id == 7
    assert db.flush.call_count == 3
    assert db.add.call_args_list[0].args[0].__class__.__name__ == "User"
    assert db.add.call_args_list[1].args[0].__class__.__name__ == "Profile"
    assert db.add.call_args_list[2].args[0].__class__.__name__ == "Employee"
    assert db.add.call_args_list[3].args[0].__class__.__name__ == "UserRole"


def test_duplicate_email_integrity_error_rolls_back_and_returns_conflict():
    from app.services.employee_service import EmployeeService

    db = MagicMock()
    repository = MagicMock()
    original = MagicMock()
    original.diag.constraint_name = "ix_users_email"
    repository.create.side_effect = IntegrityError("insert", {}, original)

    with pytest.raises(DuplicateEmailError):
        EmployeeService(db, repository).register(EmployeeCreate(**VALID_PAYLOAD))
    db.rollback.assert_called_once()


def test_duplicate_employee_code_integrity_error_is_distinguished():
    from app.services.employee_service import EmployeeService

    db = MagicMock()
    repository = MagicMock()
    original = MagicMock()
    original.diag.constraint_name = "employees_employee_code_key"
    repository.create.side_effect = IntegrityError("insert", {}, original)

    with pytest.raises(DuplicateEmployeeCodeError):
        EmployeeService(db, repository).register(EmployeeCreate(**VALID_PAYLOAD))
    db.rollback.assert_called_once()


def test_unexpected_failure_after_mutation_rolls_back_and_reraises():
    from app.services.employee_service import EmployeeService

    db = MagicMock()
    repository = MagicMock()

    def mutate_then_fail(_data):
        db.add("mutated")
        raise RuntimeError("unexpected failure")

    repository.create.side_effect = mutate_then_fail
    with pytest.raises(RuntimeError, match="unexpected failure"):
        EmployeeService(db, repository).register(EmployeeCreate(**VALID_PAYLOAD))
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_unknown_integrity_error_is_generic_and_rolled_back():
    from app.services.employee_service import EmployeeService

    db = MagicMock()
    repository = MagicMock()
    original = MagicMock()
    original.diag.constraint_name = "unknown_constraint"
    repository.create.side_effect = IntegrityError("insert", {}, original)

    with pytest.raises(PersistenceError):
        EmployeeService(db, repository).register(EmployeeCreate(**VALID_PAYLOAD))
    db.rollback.assert_called_once()
