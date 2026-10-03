# Testes do Controller

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_client_pendency_service
from app.main import app
from app.schemas.client_pendency_schema import (
    ClientPendencyResponse,
    ClientValidationResponse,
    OverdueLoanResponse,
)


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides = {}
    yield
    app.dependency_overrides = {}


class FakeUser:
    def __init__(self, user_id: int, roles: list[str]):
        self.id = user_id
        self.role_codes = roles


class FakePendencyService:
    def __init__(self):
        self.get_pendencies_mock = MagicMock()
        self.change_penalty_mock = MagicMock()
        self.validate_client_mock = MagicMock()

    def get_pendencies(self, client_id: int):
        return self.get_pendencies_mock(client_id)

    def change_penalty(
        self,
        *,
        client_id: int,
        action: str,
        reason: str,
        actor_id: int,
    ):
        return self.change_penalty_mock(
            client_id=client_id,
            action=action,
            reason=reason,
            actor_id=actor_id,
        )

    def validate_client_for_operation(self, client_id: int):
        return self.validate_client_mock(client_id)


def make_response(
    *,
    client_id: int = 42,
    has_pending: bool = True,
    is_penalized: bool = True,
):
    return ClientPendencyResponse(
        client_id=client_id,
        has_pending=has_pending,
        is_penalized=is_penalized,
        overdue_loans=[
            OverdueLoanResponse(
                loan_id=7,
                copy_id=15,
                book_id=3,
                book_title="O Pequeno Príncipe",
                loan_date="2026-09-10T14:00:00Z",
                due_date="2026-09-17T14:00:00Z",
            )
        ]
        if has_pending
        else [],
    )

# SELLER pode consultar

def test_seller_pode_consultar_pendencias():
    service = FakePendencyService()
    service.get_pendencies_mock.return_value = make_response()

    app.dependency_overrides[get_current_user] = lambda: FakeUser(
        user_id=10,
        roles=["SELLER"],
    )
    app.dependency_overrides[get_client_pendency_service] = lambda: service

    client = TestClient(app)

    response = client.get("/api/v1/clients/42/pendencies")

    assert response.status_code == 200

    data = response.json()

    assert data["client_id"] == 42
    assert data["has_pending"] is True
    assert data["is_penalized"] is True
    assert len(data["overdue_loans"]) == 1

# ADMINISTRATOR pode consultar

def test_administrator_pode_consultar_pendencias():
    service = FakePendencyService()
    service.get_pendencies_mock.return_value = make_response()

    app.dependency_overrides[get_current_user] = lambda: FakeUser(
        user_id=1,
        roles=["ADMINISTRATOR"],
    )
    app.dependency_overrides[get_client_pendency_service] = lambda: service

    client = TestClient(app)

    response = client.get("/api/v1/clients/42/pendencies")

    assert response.status_code == 200

# USER não pode consultar

def test_user_nao_pode_consultar_pendencias():
    app.dependency_overrides[get_current_user] = lambda: FakeUser(
        user_id=20,
        roles=["USER"],
    )

    client = TestClient(app)

    response = client.get("/api/v1/clients/42/pendencies")

    assert response.status_code == 403

# Sem autenticação

def test_sem_autenticacao_retorna_401():
    client = TestClient(app)

    response = client.get("/api/v1/clients/42/pendencies")

    assert response.status_code == 401

# Testes da alteração manual

# APPLY com pendência

def test_apply_penalty_com_pendencia():
    service = FakePendencyService()
    service.change_penalty_mock.return_value = make_response()

    app.dependency_overrides[get_current_user] = lambda: FakeUser(
        user_id=10,
        roles=["SELLER"],
    )
    app.dependency_overrides[get_client_pendency_service] = lambda: service

    client = TestClient(app)

    response = client.patch(
        "/api/v1/clients/42/penalty",
        json={
            "action": "APPLY",
            "reason": "Atraso identificado durante atendimento.",
        },
    )

    assert response.status_code == 200

    service.change_penalty_mock.assert_called_once_with(
        client_id=42,
        action="APPLY",
        reason="Atraso identificado durante atendimento.",
        actor_id=10,
    )

#REMOVE sem pendência

def test_remove_penalty_sem_pendencia():
    service = FakePendencyService()
    service.change_penalty_mock.return_value = make_response(
        has_pending=False,
        is_penalized=False,
    )

    app.dependency_overrides[get_current_user] = lambda: FakeUser(
        user_id=1,
        roles=["ADMINISTRATOR"],
    )
    app.dependency_overrides[get_client_pendency_service] = lambda: service

    client = TestClient(app)

    response = client.patch(
        "/api/v1/clients/42/penalty",
        json={
            "action": "REMOVE",
            "reason": "Empréstimo regularizado.",
        },
    )

    assert response.status_code == 200

# USER não pode alterar

def test_user_nao_pode_alterar_penalizacao():
    app.dependency_overrides[get_current_user] = lambda: FakeUser(
        user_id=20,
        roles=["USER"],
    )

    client = TestClient(app)

    response = client.patch(
        "/api/v1/clients/42/penalty",
        json={
            "action": "APPLY",
            "reason": "Motivo válido",
        },
    )

    assert response.status_code == 403

# Motivo muito curto

def test_penalty_reason_invalido():
    app.dependency_overrides[get_current_user] = lambda: FakeUser(
        user_id=10,
        roles=["SELLER"],
    )

    client = TestClient(app)

    response = client.patch(
        "/api/v1/clients/42/penalty",
        json={
            "action": "APPLY",
            "reason": "a",
        },
    )

    assert response.status_code == 422

# Testes do Service

# Pendência gera penalização
def test_pendencia_sincroniza_penalizacao():
    db = MagicMock()
    repository = MagicMock()

    client = MagicMock()
    client.id = 42
    client.is_penalized = False

    repository.find_client_for_update.return_value = client
    repository.list_overdue_loans.return_value = [
        {
            "loan_id": 7,
            "copy_id": 15,
            "book_id": 3,
            "book_title": "O Pequeno Príncipe",
            "loan_date": "2026-09-10T14:00:00Z",
            "due_date": "2026-09-17T14:00:00Z",
        }
    ]

    from app.services.client_pendency_service import ClientPendencyService

    service = ClientPendencyService(
        db=db,
        repository=repository,
    )

    result = service.get_pendencies(42)

    assert result.has_pending is True
    assert result.is_penalized is True

    repository.update_penalized.assert_called_once_with(
        client,
        True,
    )

    repository.record_penalty_change.assert_called_once()

    db.commit.assert_called_once()

# Sem pendência remove penalização

def test_sem_pendencia_remove_penalizacao():
    db = MagicMock()
    repository = MagicMock()

    client = MagicMock()
    client.id = 42
    client.is_penalized = True

    repository.find_client_for_update.return_value = client
    repository.list_overdue_loans.return_value = []

    from app.services.client_pendency_service import ClientPendencyService

    service = ClientPendencyService(
        db=db,
        repository=repository,
    )

    result = service.get_pendencies(42)

    assert result.has_pending is False
    assert result.is_penalized is False

    repository.update_penalized.assert_called_once_with(
        client,
        False,
    )

    db.commit.assert_called_once()

# Vários atrasos mantêm a penalização

def test_varios_atrasos_mantem_penalizacao():
    db = MagicMock()
    repository = MagicMock()

    client = MagicMock()
    client.id = 42
    client.is_penalized = True

    repository.find_client_for_update.return_value = client
    repository.list_overdue_loans.return_value = [
        {
            "loan_id": 7,
            "copy_id": 15,
            "book_id": 3,
            "book_title": "Livro A",
            "loan_date": "2026-09-01T14:00:00Z",
            "due_date": "2026-09-10T14:00:00Z",
        },
        {
            "loan_id": 8,
            "copy_id": 16,
            "book_id": 4,
            "book_title": "Livro B",
            "loan_date": "2026-09-02T14:00:00Z",
            "due_date": "2026-09-11T14:00:00Z",
        },
    ]

    from app.services.client_pendency_service import ClientPendencyService

    service = ClientPendencyService(
        db=db,
        repository=repository,
    )

    result = service.get_pendencies(42)

    assert len(result.overdue_loans) == 2
    assert result.has_pending is True
    assert result.is_penalized is True

    repository.update_penalized.assert_not_called()

# APPLY e REMOVE

# Não pode aplicar sem pendência
def test_apply_sem_pendencia_retorna_erro():
    db = MagicMock()
    repository = MagicMock()

    employee = MagicMock()

    client = MagicMock()
    client.id = 42
    client.is_penalized = False

    repository.find_employee_by_id.return_value = employee
    repository.find_client_for_update.return_value = client
    repository.list_overdue_loans.return_value = []

    from app.services.client_pendency_service import ClientPendencyService
    from app.core.exceptions import ClientPenaltyApplicationError

    service = ClientPendencyService(
        db=db,
        repository=repository,
    )

    with pytest.raises(ClientPenaltyApplicationError):
        service.change_penalty(
            client_id=42,
            action="APPLY",
            reason="Motivo válido",
            actor_id=10,
        )

    db.rollback.assert_called_once()

# Não pode remover com pendência
def test_remove_com_pendencia_retorna_erro():
    db = MagicMock()
    repository = MagicMock()

    employee = MagicMock()

    client = MagicMock()
    client.id = 42
    client.is_penalized = True

    repository.find_employee_by_id.return_value = employee
    repository.find_client_for_update.return_value = client
    repository.list_overdue_loans.return_value = [
        {
            "loan_id": 7,
            "copy_id": 15,
            "book_id": 3,
            "book_title": "Livro",
            "loan_date": "2026-09-01T14:00:00Z",
            "due_date": "2026-09-10T14:00:00Z",
        }
    ]

    from app.services.client_pendency_service import ClientPendencyService
    from app.core.exceptions import ClientPenaltyRemovalError

    service = ClientPendencyService(
        db=db,
        repository=repository,
    )

    with pytest.raises(ClientPenaltyRemovalError):
        service.change_penalty(
            client_id=42,
            action="REMOVE",
            reason="Motivo válido",
            actor_id=10,
        )

    db.rollback.assert_called_once()

# Histórico

def test_penalizacao_manual_registra_funcionario_no_historico():
    db = MagicMock()
    repository = MagicMock()

    employee = MagicMock()

    client = MagicMock()
    client.id = 42
    client.is_penalized = False

    repository.find_employee_by_id.return_value = employee
    repository.find_client_for_update.return_value = client
    repository.list_overdue_loans.return_value = [
    {
        "loan_id": 7,
        "copy_id": 15,
        "book_id": 3,
        "book_title": "O Pequeno Príncipe",
        "loan_date": "2026-09-10T14:00:00Z",
        "due_date": "2026-09-17T14:00:00Z",
    }
]

    from app.services.client_pendency_service import ClientPendencyService

    service = ClientPendencyService(
        db=db,
        repository=repository,
    )

    service.change_penalty(
        client_id=42,
        action="APPLY",
        reason="Atraso identificado.",
        actor_id=10,
    )

    repository.record_penalty_change.assert_called_once()

    kwargs = repository.record_penalty_change.call_args.kwargs

    assert kwargs["actor_type"] == "EMPLOYEE"
    assert kwargs["employee_id"] == 10
    assert kwargs["old_value"] is False
    assert kwargs["new_value"] is True
    assert kwargs["reason"] == "Atraso identificado."

# E para a automática:

def test_sincronizacao_automatica_registra_system():
    db = MagicMock()
    repository = MagicMock()

    client = MagicMock()
    client.id = 42
    client.is_penalized = False

    repository.find_client_for_update.return_value = client
    repository.list_overdue_loans.return_value = [
    {
        "loan_id": 7,
        "copy_id": 15,
        "book_id": 3,
        "book_title": "O Pequeno Príncipe",
        "loan_date": "2026-09-10T14:00:00Z",
        "due_date": "2026-09-17T14:00:00Z",
    }
]

    from app.services.client_pendency_service import ClientPendencyService

    service = ClientPendencyService(
        db=db,
        repository=repository,
    )

    service.get_pendencies(42)

    kwargs = repository.record_penalty_change.call_args.kwargs

    assert kwargs["actor_type"] == "SYSTEM"
    assert kwargs["employee_id"] is None

# Concorrência e transação

def test_repository_nao_controla_transacao():
    db = MagicMock()

    from app.repositories.client_pendency_repository import (
        ClientPendencyRepository,
    )

    repository = ClientPendencyRepository(db)

    client = MagicMock()
    client.id = 42

    repository.update_penalized(client, True)

    db.commit.assert_not_called()
    db.rollback.assert_not_called()

# Testes da validação da situação do cliente

def test_cliente_ativo_sem_pendencia_eh_aprovado():
    db = MagicMock()
    repository = MagicMock()

    client = MagicMock()
    client.id = 42
    client.is_penalized = False

    repository.find_client_for_update.return_value = client
    repository.find_user_active.return_value = True
    repository.list_overdue_loans.return_value = []

    from app.services.client_pendency_service import ClientPendencyService

    service = ClientPendencyService(
        db=db,
        repository=repository,
    )

    result = service.validate_client_for_operation(42)

    assert result.client_id == 42
    assert result.valid is True


def test_cliente_inativo_eh_bloqueado():
    db = MagicMock()
    repository = MagicMock()

    client = MagicMock()
    client.id = 42
    client.is_penalized = False

    repository.find_client_for_update.return_value = client
    repository.find_user_active.return_value = False

    from app.services.client_pendency_service import ClientPendencyService
    from app.core.exceptions import ClientInactiveError

    service = ClientPendencyService(
        db=db,
        repository=repository,
    )

    with pytest.raises(ClientInactiveError):
        service.validate_client_for_operation(42)

    repository.list_overdue_loans.assert_not_called()
    db.rollback.assert_called_once()


def test_cliente_com_pendencia_eh_bloqueado():
    db = MagicMock()
    repository = MagicMock()

    client = MagicMock()
    client.id = 42
    client.is_penalized = False

    repository.find_client_for_update.return_value = client
    repository.find_user_active.return_value = True
    repository.list_overdue_loans.return_value = [
        {
            "loan_id": 7,
            "copy_id": 15,
            "book_id": 3,
            "book_title": "Livro",
            "loan_date": "2026-09-10T14:00:00Z",
            "due_date": "2026-09-17T14:00:00Z",
        }
    ]

    from app.services.client_pendency_service import ClientPendencyService
    from app.core.exceptions import ClientHasPendingError

    service = ClientPendencyService(
        db=db,
        repository=repository,
    )

    with pytest.raises(ClientHasPendingError):
        service.validate_client_for_operation(42)

    repository.list_overdue_loans.assert_called_once_with(42)
    db.rollback.assert_called_once()


def test_cliente_inexistente_eh_rejeitado():
    db = MagicMock()
    repository = MagicMock()

    repository.find_client_for_update.return_value = None

    from app.services.client_pendency_service import ClientPendencyService
    from app.core.exceptions import ClientNotFoundError

    service = ClientPendencyService(
        db=db,
        repository=repository,
    )

    with pytest.raises(ClientNotFoundError):
        service.validate_client_for_operation(42)

    repository.find_user_active.assert_not_called()
    db.rollback.assert_called_once()

def test_validacao_cliente_ativo_sem_pendencia_retorna_200():
    service = FakePendencyService()
    service.validate_client_mock.return_value = ClientValidationResponse(
        client_id=42,
        valid=True,
    )

    app.dependency_overrides[get_current_user] = lambda: FakeUser(
        user_id=10,
        roles=["SELLER"],
    )
    app.dependency_overrides[get_client_pendency_service] = lambda: service

    client = TestClient(app)

    response = client.get("/api/v1/clients/42/validation")

    assert response.status_code == 200
    assert response.json() == {
        "client_id": 42,
        "valid": True,
    }

    service.validate_client_mock.assert_called_once_with(42)


def test_validacao_cliente_inativo_retorna_403():
    service = FakePendencyService()

    from app.core.exceptions import ClientInactiveError

    service.validate_client_mock.side_effect = ClientInactiveError()

    app.dependency_overrides[get_current_user] = lambda: FakeUser(
        user_id=10,
        roles=["SELLER"],
    )
    app.dependency_overrides[get_client_pendency_service] = lambda: service

    client = TestClient(app)

    response = client.get("/api/v1/clients/42/validation")

    assert response.status_code == 403
    assert response.json()["code"] == "client_inactive"


def test_validacao_cliente_com_pendencia_retorna_409():
    service = FakePendencyService()

    from app.core.exceptions import ClientHasPendingError

    service.validate_client_mock.side_effect = ClientHasPendingError()

    app.dependency_overrides[get_current_user] = lambda: FakeUser(
        user_id=10,
        roles=["SELLER"],
    )
    app.dependency_overrides[get_client_pendency_service] = lambda: service

    client = TestClient(app)

    response = client.get("/api/v1/clients/42/validation")

    assert response.status_code == 409
    assert response.json()["code"] == "client_has_pending"


def test_user_nao_autorizado_nao_pode_validar_cliente():
    app.dependency_overrides[get_current_user] = lambda: FakeUser(
        user_id=20,
        roles=["USER"],
    )

    client = TestClient(app)

    response = client.get("/api/v1/clients/42/validation")

    assert response.status_code == 403