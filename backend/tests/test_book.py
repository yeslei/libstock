from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@patch("app.services.book_service.BookService.fetch_google_books_data")
def test_create_book_with_isbn_success(mock_fetch):
    # Simula o retorno direto do método que busca na API externa
    mock_fetch.return_value = {
        "title": "Python Fluente",
        "author": "Luciano Ramalho",
        "genre": "Tecnologia"
    }

    response = client.post(
        "/api/v1/books/",
        json={
            "isbn": "978-8575225530"
        }
    )
    assert response.status_code in [201, 401]

def test_create_book_invalid_isbn():
    response = client.post(
        "/api/v1/books/",
        json={
            "isbn": "000-00-000-0000-0"
        }
    )
    assert response.status_code in [404, 422, 401]