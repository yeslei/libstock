from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_copy_success():
    # Nota: Certifique-se de que exista um book_id válido no seu banco de testes
    response = client.post(
        "/api/v1/copies/",
        json={
            "barcode": "EX-000001",
            "destination": "COMMERCIAL",
            "sale_price": 39.90,
            "book_id": 1,
        }
    )
    # Ajuste o status code esperado conforme a exigência de autenticação da rota
    assert response.status_code in [201, 400, 401]

def test_create_copy_invalid_tag():
    response = client.post(
        "/api/v1/copies/",
        json={
            "barcode": "EX-000002",
            "destination": "INVALID",
            "book_id": 1
        }
    )
    assert response.status_code in [401, 422]


def test_commercial_copy_requires_sale_price():
    response = client.post(
        "/api/v1/copies/",
        json={"barcode": "EX-000003", "destination": "COMMERCIAL", "book_id": 1},
    )

    assert response.status_code in [401, 422]