from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_employee_mock():
    response = client.post(
        "/api/v1/employees/",
        json={
            "name": "Teste Unitario",
            "email": "teste@example.com",
            "password": "senha123",
            "accessLevel": "Atendente"
        }
    )
    assert response.status_code == 201
    assert response.json()["employee_data"]["name"] == "Teste Unitario"