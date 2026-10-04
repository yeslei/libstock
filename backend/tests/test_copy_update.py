"""Edição/conversão de exemplar (Issue #151): contrato HTTP e regras do service com repositório simulado."""
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import InternalError

from app.controllers.copy_controller import get_copy_service
from app.core.exceptions import (
    CopyNotFoundError,
    CopySalePriceNotAllowedError,
    CopySalePriceRequiredError,
    CopyUpdateBlockedError,
    CopyUpdatePersistenceError,
    EmployeeRecordRequiredError,
    PermissionDeniedError,
)
from app.dependencies.authentication import get_current_user
from app.main import app
from app.models.domain import CopyStatus, DestinationType
from app.schemas.copy_schema import CopyUpdate
from app.services.copy_service import CopyService


class FakeRepository:
    def __init__(self, copy, *, employee=True, allocated=False, open_sale=False, apply_error=None,
                 pending_request=False, other_free=True):
        self.pending_request = pending_request
        self.other_free = other_free
        self.copy = copy
        self.employee = employee
        self.allocated = allocated
        self.open_sale = open_sale
        self.apply_error = apply_error
        self.calls = []

    def is_active_employee(self, user_id):
        self.calls.append(f"is_active_employee({user_id})")
        return self.employee

    def set_audit_actor(self, employee_id):
        self.calls.append(f"set_audit_actor({employee_id})")

    def find_copy(self, copy_id):
        self.calls.append(f"find_copy({copy_id})")
        return self.copy

    def lock_book(self, book_id):
        self.calls.append(f"lock_book({book_id})")

    def lock_copy(self, copy_id):
        self.calls.append(f"lock_copy({copy_id})")
        return self.copy

    def is_allocated_to_reservation(self, _copy_id):
        return self.allocated

    def has_open_sale(self, _copy_id):
        return self.open_sale

    def has_pending_loan_request(self, _book_id):
        return self.pending_request

    def has_other_free_didactic_copy(self, _book_id, _copy_id):
        return self.other_free

    def apply_copy_changes(self, copy, changes):
        self.calls.append(f"apply({sorted(changes)})")
        if self.apply_error:
            raise self.apply_error
        for key, value in changes.items():
            setattr(copy, key, value)
        return copy


class FakeSession:
    def __init__(self):
        self.commits = self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, _obj):
        pass


def a_copy(**over):
    values = dict(id=9, book_id=1, barcode="EX-9", status=CopyStatus.AVAILABLE, is_active=True,
                  destination=DestinationType.DIDACTIC, sale_price=None, condition=None, acquired_at=None)
    values.update(over)
    return SimpleNamespace(**values)


def update(repository, payload, session=None):
    session = session or FakeSession()
    return CopyService(repository, session).update_copy(9, CopyUpdate(**payload), 7), session


def test_conversion_locks_book_before_copy_and_commits_once():
    repository = FakeRepository(a_copy())
    copy, session = update(repository, {"destination": DestinationType.COMMERCIAL, "sale_price": Decimal("19.90")})
    assert (copy.destination, copy.sale_price) == (DestinationType.COMMERCIAL, Decimal("19.90"))
    assert (session.commits, session.rollbacks) == (1, 0)
    assert repository.calls[:5] == ["is_active_employee(7)", "set_audit_actor(7)", "find_copy(9)", "lock_book(1)", "lock_copy(9)"]


def test_conversion_to_didactic_clears_price_and_code_is_never_part_of_the_change():
    repository = FakeRepository(a_copy(destination=DestinationType.COMMERCIAL, sale_price=Decimal("20")))
    copy, _ = update(repository, {"destination": DestinationType.DIDACTIC})
    assert (copy.destination, copy.sale_price, copy.barcode) == (DestinationType.DIDACTIC, None, "EX-9")
    assert "barcode" not in repository.calls[-1]


@pytest.mark.parametrize("copy,payload,error", [
    (a_copy(), {"destination": DestinationType.COMMERCIAL}, CopySalePriceRequiredError),
    (a_copy(), {"destination": DestinationType.COMMERCIAL, "sale_price": Decimal("0")}, CopySalePriceRequiredError),
    (a_copy(destination=DestinationType.COMMERCIAL, sale_price=Decimal("5")), {"sale_price": Decimal("0")}, CopySalePriceRequiredError),
    (a_copy(), {"sale_price": Decimal("5")}, CopySalePriceNotAllowedError),
])
def test_price_rules_return_stable_422(copy, payload, error):
    session = FakeSession()
    with pytest.raises(error) as raised:
        update(FakeRepository(copy), payload, session)
    assert raised.value.status_code == 422
    assert (session.commits, session.rollbacks) == (0, 1)


@pytest.mark.parametrize("copy,kwargs,codes", [
    (a_copy(status=CopyStatus.BORROWED), {}, ["copy_not_available"]),
    (a_copy(status=CopyStatus.SOLD), {}, ["copy_not_available"]),
    (a_copy(is_active=False), {}, ["copy_inactive"]),
    (a_copy(), {"allocated": True}, ["copy_allocated"]),
    (a_copy(), {"open_sale": True}, ["copy_in_operation"]),
    (a_copy(is_active=False, status=CopyStatus.BORROWED), {"allocated": True}, ["copy_inactive", "copy_not_available", "copy_allocated"]),
])
def test_blocked_copies_return_409_with_all_reasons_and_change_nothing(copy, kwargs, codes):
    repository = FakeRepository(copy, **kwargs)
    session = FakeSession()
    with pytest.raises(CopyUpdateBlockedError) as raised:
        update(repository, {"condition": "Bom"}, session)
    assert (raised.value.status_code, raised.value.code) == (409, codes[0])
    assert [reason["code"] for reason in raised.value.details["reasons"]] == codes
    assert not any(call.startswith("apply") for call in repository.calls)
    assert (session.commits, session.rollbacks) == (0, 1)


def test_last_free_didactic_copy_with_pending_pickup_request_cannot_become_commercial():
    repository = FakeRepository(a_copy(), pending_request=True, other_free=False)
    session = FakeSession()
    with pytest.raises(CopyUpdateBlockedError) as raised:
        update(repository, {"destination": DestinationType.COMMERCIAL, "sale_price": Decimal("10")}, session)
    assert (raised.value.status_code, raised.value.code) == (409, "copy_needed_for_requests")
    assert not any(call.startswith("apply") for call in repository.calls)
    assert (session.commits, session.rollbacks) == (0, 1)


@pytest.mark.parametrize("kwargs", [{"pending_request": False, "other_free": False}, {"pending_request": True, "other_free": True}])
def test_conversion_is_allowed_without_pending_request_or_with_another_free_copy(kwargs):
    copy, _ = update(FakeRepository(a_copy(), **kwargs), {"destination": DestinationType.COMMERCIAL, "sale_price": Decimal("10")})
    assert copy.destination == DestinationType.COMMERCIAL


def test_missing_copy_inactive_employee_and_noop():
    with pytest.raises(CopyNotFoundError):
        update(FakeRepository(None), {"condition": "Bom"})

    class Vanishing(FakeRepository):
        def lock_copy(self, copy_id):
            return None

    with pytest.raises(CopyNotFoundError):
        update(Vanishing(a_copy()), {"condition": "Bom"})
    repository = FakeRepository(a_copy(), employee=False)
    with pytest.raises(EmployeeRecordRequiredError):
        update(repository, {"condition": "Bom"})
    assert repository.calls == ["is_active_employee(7)"]
    noop = FakeRepository(a_copy(condition="Bom"))
    _, session = update(noop, {"condition": "Bom"})
    assert not any(call.startswith("apply") for call in noop.calls) and session.commits == 1


class DbOrig(Exception):
    def __init__(self, sqlstate=None, message=None, constraint=None):
        super().__init__(message or "erro")
        self.sqlstate = sqlstate
        self.diag = SimpleNamespace(message_primary=message, constraint_name=constraint)


@pytest.mark.parametrize("orig,error", [
    (DbOrig(message="An allocated copy cannot change book, destination, activity or availability"), CopyUpdateBlockedError),
    (DbOrig(sqlstate="LS002"), CopyUpdateBlockedError),
    (DbOrig(sqlstate="LS001"), PermissionDeniedError),
    (DbOrig(constraint="chk_commercial_price"), CopySalePriceRequiredError),
    (DbOrig(constraint="chk_didactic_without_sale_price"), CopySalePriceNotAllowedError),
    (DbOrig(message="qualquer outra falha"), CopyUpdatePersistenceError),
    (DbOrig(message="texto parecido: Changing destination requires"), CopyUpdatePersistenceError),
])
def test_database_barriers_never_surface_as_a_raw_500(orig, error):
    repository = FakeRepository(a_copy(), apply_error=InternalError("UPDATE", {}, orig))
    session = FakeSession()
    with pytest.raises(error):
        update(repository, {"condition": "Bom"}, session)
    assert (session.commits, session.rollbacks) == (0, 1)


# --- contrato HTTP ----------------------------------------------------------------------------------

class StubService:
    def __init__(self):
        self.calls = []

    def update_copy(self, copy_id, changes, actor_id):
        self.calls.append((copy_id, changes.model_dump(exclude_unset=True), actor_id))
        return {"id": copy_id, "book_id": 1, "barcode": "EX-9", "destination": "DIDACTIC", "condition": None,
                "sale_price": None, "acquired_at": None, "status": "AVAILABLE", "is_active": True}


@pytest.fixture
def http():
    yield TestClient(app)
    app.dependency_overrides.clear()


def as_user(roles):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role_codes=roles)


def test_http_without_token_is_401(http):
    app.dependency_overrides[get_copy_service] = StubService
    assert http.patch("/api/v1/copies/9", json={"condition": "Bom"}).status_code == 401


@pytest.mark.parametrize("role", ["USER", "MANAGER"])
def test_http_roles_without_permission_are_403_and_do_not_call_the_service(http, role):
    service = StubService()
    app.dependency_overrides[get_copy_service] = lambda: service
    as_user([role])
    response = http.patch("/api/v1/copies/9", json={"condition": "Bom"})
    assert (response.status_code, response.json()["code"]) == (403, "permission_denied")
    assert service.calls == []


@pytest.mark.parametrize("role", ["SELLER", "STOCK_KEEPER", "ADMINISTRATOR"])
def test_http_authorized_roles_update_with_200(http, role):
    service = StubService()
    app.dependency_overrides[get_copy_service] = lambda: service
    as_user([role])
    response = http.patch("/api/v1/copies/9", json={"condition": "Bom"})
    assert response.status_code == 200 and service.calls == [(9, {"condition": "Bom"}, 7)]


@pytest.mark.parametrize("payload", [
    {}, {"barcode": "NOVO"}, {"destination": "DIDACTIC", "sale_price": "10"}, {"sale_price": "-1"},
    {"destination": None}, {"status": "SOLD"},
])
def test_http_invalid_payloads_are_422(http, payload):
    service = StubService()
    app.dependency_overrides[get_copy_service] = lambda: service
    as_user(["SELLER"])
    assert http.patch("/api/v1/copies/9", json=payload).status_code == 422
    assert service.calls == []
