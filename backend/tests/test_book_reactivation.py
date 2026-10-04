"""Reativação de obra (Issue #151): regra do service e contrato HTTP."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import InternalError

from app.core.exceptions import BookWithoutActiveCopyError, EmployeeRecordRequiredError
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_book_service
from app.main import app
from app.schemas.book_schema import BookUpdate
from app.services.book_service import BookService


class Repository:
    def __init__(self, *, active=False, has_copy=True, employee=True):
        self.db = MagicMock()
        self.book = SimpleNamespace(
            id=1, isbn=None, title="Obra", author="Autora", genre=None, cover_url=None,
            is_active=active, initial_copy=None, copies=[],
        )
        self.has_copy = has_copy
        self.employee = employee
        self.calls = []

    def employee_exists(self, _id):
        return self.employee

    def get_with_copies(self, _id):
        return self.book

    def find_by_isbn_except(self, *_args):
        return None

    def lock_book_for_inactivation(self, book_id):
        self.calls.append(f"lock({book_id})")

    def has_active_copy(self, book_id):
        self.calls.append(f"has_active_copy({book_id})")
        return self.has_copy

    def update_book(self, book, changes):
        self.calls.append("update")
        for key, value in changes.model_dump(exclude_unset=True).items():
            setattr(book, key, value)
        return book


def service(repository):
    return BookService(db=repository.db, repository=repository)


def test_reactivation_with_an_active_copy_locks_checks_and_commits():
    repository = Repository(has_copy=True)
    response = service(repository).update_book(1, BookUpdate(is_active=True), employee_id=9)
    assert response.is_active is True
    assert repository.calls == ["lock(1)", "has_active_copy(1)", "update"]
    repository.db.commit.assert_called_once()


def test_reactivation_without_active_copy_is_409_and_rolls_back():
    repository = Repository(has_copy=False)
    with pytest.raises(BookWithoutActiveCopyError) as error:
        service(repository).update_book(1, BookUpdate(is_active=True), employee_id=9)
    assert (error.value.status_code, error.value.code) == (409, "book_without_active_copy")
    assert repository.book.is_active is False and "update" not in repository.calls
    repository.db.rollback.assert_called_once()
    repository.db.commit.assert_not_called()


def test_other_changes_to_an_active_book_do_not_check_copies():
    repository = Repository(active=True)
    service(repository).update_book(1, BookUpdate(is_active=True, genre="Romance"), employee_id=9)
    assert "has_active_copy(1)" not in repository.calls


def test_trigger_failure_on_commit_is_mapped_to_the_domain_error():
    repository = Repository(has_copy=True)
    repository.db.commit.side_effect = InternalError(
        "UPDATE", {}, Exception("An active book requires at least one active copy"))
    with pytest.raises(BookWithoutActiveCopyError):
        service(repository).update_book(1, BookUpdate(is_active=True), employee_id=9)
    repository.db.rollback.assert_called_once()


def test_inactive_employee_cannot_reactivate():
    repository = Repository(employee=False)
    with pytest.raises(EmployeeRecordRequiredError):
        service(repository).update_book(1, BookUpdate(is_active=True), employee_id=9)
    assert repository.calls == []


class Stub:
    def update_book(self, _book_id, _changes, *, employee_id, can_view_clients):
        return {"id": 1, "isbn": None, "title": "Obra", "author": "A", "genre": None, "cover_url": None,
                "is_active": True, "initial_copy": None, "copies": []}


@pytest.mark.parametrize("roles,status", [
    (["SELLER"], 200), (["STOCK_KEEPER"], 200), (["ADMINISTRATOR"], 200), (["USER"], 403),
])
def test_http_reactivation_roles(roles, status):
    app.dependency_overrides[get_book_service] = Stub
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role_codes=roles)
    try:
        response = TestClient(app).patch("/api/v1/books/1", json={"is_active": True})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == status
