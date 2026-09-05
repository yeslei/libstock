from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.dependencies.authentication import get_current_user
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _autentica_como_administrador():
    """A rota passou a exigir ADMINISTRATOR (RF06): definir nível de acesso
    é operação privativa. O caso sem permissão vive em `test_catalog.py`."""
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1,
        name="Admin",
        email="admin@libstock.com.br",
        role_codes=["ADMINISTRATOR"],
    )
    yield
    app.dependency_overrides.clear()


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
