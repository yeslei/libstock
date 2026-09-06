from fastapi.testclient import TestClient

from app.dependencies.services import get_book_service
from app.main import app


class StubBookService:
    def search_books(self, title: str) -> list[dict[str, object]]:
        return [{"id": 1, "title": title, "author": "Author", "is_active": True}]


def test_search_books_success_and_response_serialization() -> None:
    app.dependency_overrides[get_book_service] = StubBookService
    try:
        response = TestClient(app).get("/api/v1/books/?title=Hobbit")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "isbn": None, "title": "Hobbit", "author": "Author", "genre": None, "is_active": True, "initial_copy": None}
    ]


def test_search_books_rejects_blank_title() -> None:
    app.dependency_overrides[get_book_service] = StubBookService
    try:
        response = TestClient(app).get("/api/v1/books/?title=%20%20%20")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_search_books_is_public_without_authorization_header() -> None:
    app.dependency_overrides[get_book_service] = StubBookService
    try:
        response = TestClient(app).get("/api/v1/books/?title=Hobbit")
    finally:
        app.dependency_overrides.clear()

    assert "Authorization" not in response.request.headers
    assert response.status_code == 200


def test_create_book_openapi_forbids_additional_properties() -> None:
    schema = app.openapi()["components"]["schemas"]["BookCreate"]

    assert schema["additionalProperties"] is False
