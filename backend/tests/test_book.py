from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@patch("app.services.book_service.BookService.lookup_google_books")
def test_lookup_book_by_isbn(mock_lookup):
    mock_lookup.return_value = {
        "isbn": "9788575225530",
        "title": "Python Fluente",
        "author": "Luciano Ramalho",
        "genre": "Tecnologia",
        "publication_year": 2015,
        "publisher": "Novatec",
        "edition": None,
        "cover_url": None,
    }

    response = client.get("/api/v1/books/lookup?isbn=9788575225530")

    assert response.status_code == 200
    assert response.json()["title"] == "Python Fluente"
    mock_lookup.assert_called_once_with("9788575225530")


def test_create_book_requires_data_filled_by_form():
    response = client.post("/api/v1/books/", json={"isbn": "9788575225530"})

    assert response.status_code == 422

def test_create_book_invalid_isbn():
    response = client.get("/api/v1/books/lookup?isbn=000-00-000-0000-0")

    assert response.status_code in [404, 502]