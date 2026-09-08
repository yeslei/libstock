from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from fastapi.testclient import TestClient

from app.core.exceptions import BookNotFoundError, BookUpdatePersistenceError, DuplicateIsbnError
from app.schemas.book_schema import BookCreate, BookUpdate
from app.services.book_service import BookService
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_book_service
from app.main import app


def test_cover_url_accepts_http_and_https() -> None:
    base = {"isbn": "9788575225530", "title": "Obra", "author": "Autora", "initial_copy": {"barcode": "A-1", "destination": "DIDACTIC"}}
    assert BookCreate(**base, cover_url="https://img.example/capa.jpg").cover_url.startswith("https://")
    with pytest.raises(ValidationError):
        BookCreate(**base, cover_url="javascript:alert(1)")


class ManagementRepository:
    def __init__(self, book=None):
        self.db = MagicMock()
        self.book = book
        self.updated = None

    def employee_exists(self, _employee_id): return True
    def get_with_copies(self, _book_id): return self.book
    def find_by_isbn_except(self, _isbn, _book_id): return None
    def update_book(self, book, changes):
        self.updated = changes
        for key, value in changes.model_dump(exclude_unset=True).items(): setattr(book, key, value)
        return book


def make_book():
    return SimpleNamespace(id=1, isbn="9788575225530", title="Antes", author="Autora", genre=None, cover_url=None, is_active=True, initial_copy=None, copies=[])


def test_update_book_persists_and_audits_actor() -> None:
    repository = ManagementRepository(make_book())
    service = BookService(db=repository.db, repository=repository)
    result = service.update_book(1, BookUpdate(title="Depois", cover_url="https://img.example/capa.jpg"), employee_id=9)
    assert result.title == "Depois"
    assert result.cover_url == "https://img.example/capa.jpg"
    repository.db.execute.assert_called_once()
    repository.db.commit.assert_called_once()


def test_update_missing_book_returns_404() -> None:
    repository = ManagementRepository()
    with pytest.raises(BookNotFoundError):
        BookService(db=repository.db, repository=repository).update_book(404, BookUpdate(title="Obra"), employee_id=9)
    repository.db.rollback.assert_called_once()


def test_update_duplicate_isbn_returns_conflict() -> None:
    repository = ManagementRepository(make_book())
    repository.find_by_isbn_except = lambda *_args: object()
    with pytest.raises(DuplicateIsbnError):
        BookService(db=repository.db, repository=repository).update_book(1, BookUpdate(isbn="9788575225530"), employee_id=9)


def test_update_failure_rolls_back() -> None:
    repository = ManagementRepository(make_book())
    repository.update_book = lambda *_args: (_ for _ in ()).throw(SQLAlchemyError("falha"))
    with pytest.raises(BookUpdatePersistenceError):
        BookService(db=repository.db, repository=repository).update_book(1, BookUpdate(title="Depois"), employee_id=9)
    repository.db.rollback.assert_called_once()


class ManagementServiceStub:
    detail = {
        "id": 1, "isbn": "9788575225530", "title": "Obra", "author": "Autora",
        "genre": None, "cover_url": None, "is_active": True, "initial_copy": None,
        "copies": [],
    }

    def get_book(self, _book_id): return self.detail
    def update_book(self, _book_id, _changes, *, employee_id):
        assert employee_id == 7
        return {**self.detail, "title": "Atualizada"}
    async def lookup_metadata(self, isbn):
        return {"isbn": isbn, "title": "Título API", "author": "Autor API", "genre": "Tecnologia"}


@pytest.mark.parametrize("method,path", [("get", "/api/v1/books/1"), ("patch", "/api/v1/books/1")])
def test_management_endpoints_reject_seller(method, path) -> None:
    app.dependency_overrides[get_book_service] = ManagementServiceStub
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role_codes=["SELLER"])
    try:
        client = TestClient(app)
        response = client.get(path) if method == "get" else client.patch(path, json={"title": "Atualizada"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_stock_keeper_can_read_and_update_book() -> None:
    app.dependency_overrides[get_book_service] = ManagementServiceStub
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role_codes=["STOCK_KEEPER"])
    try:
        client = TestClient(app)
        assert client.get("/api/v1/books/1").status_code == 200
        response = client.patch("/api/v1/books/1", json={"title": "Atualizada"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["title"] == "Atualizada"


def test_stock_keeper_can_lookup_metadata_without_route_conflict() -> None:
    app.dependency_overrides[get_book_service] = ManagementServiceStub
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role_codes=["STOCK_KEEPER"])
    try:
        response = TestClient(app).get("/api/v1/books/metadata/9788575225530")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["title"] == "Título API"
