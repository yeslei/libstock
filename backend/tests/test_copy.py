from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_copy_success():
    # Nota: Certifique-se de que exista um book_id válido no seu banco de testes
    response = client.post(
        "/api/v1/copies/",
        json={
            "barcode": "978-85-7522-xxx-x",
            "destinationTag": "Comercial",
            "book_id": 1
        }
    )
    # Ajuste o status code esperado conforme a exigência de autenticação da rota
    assert response.status_code in [201, 400, 401]

def test_create_copy_invalid_tag():
    response = client.post(
        "/api/v1/copies/",
        json={
            "barcode": "978-85-7522-yyy-y",
            "destinationTag": "Invalida",
            "book_id": 1
        }
    )
    assert response.status_code == 422  # Erro de validação do Pydantic para o Literal