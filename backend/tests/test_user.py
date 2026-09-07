"""Testes da funcionalidade de inativação lógica de usuário (EAP-1.2.5).

Cobre controller, service e repository com mocks — sem banco real.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import (
    UserAlreadyInactiveError,
    UserInactiveError,
    UserNotFoundError,
    UserSelfInactivationError,
)
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_user_service
from app.main import app
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(
    *,
    user_id: int = 1,
    role_codes: list[str] | None = None,
    is_active: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        name="Teste",
        email="teste@example.com",
        is_active=is_active,
        role_codes=role_codes or ["USER"],
        updated_at=datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc),
    )


class FakeUserService:
    def __init__(self, *, error: Exception | None = None, user: SimpleNamespace | None = None) -> None:
        self.error = error
        self._user = user or _make_user(is_active=False, role_codes=["USER"])
        self.calls: list[tuple[int, int]] = []

    def get_by_id(self, user_id: int) -> SimpleNamespace:
        return self._user

    def inactivate_user(self, target_id: int, *, actor_id: int) -> SimpleNamespace:
        self.calls.append((target_id, actor_id))
        if self.error:
            raise self.error
        return self._user


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()


def _authenticate_as(*role_codes: str, user_id: int = 99) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user(
        user_id=user_id, role_codes=list(role_codes)
    )


def _use_fake_service(
    error: Exception | None = None,
    user: SimpleNamespace | None = None,
) -> FakeUserService:
    fake = FakeUserService(error=error, user=user)
    app.dependency_overrides[get_user_service] = lambda: fake
    return fake


# ---------------------------------------------------------------------------
# Controller — PATCH /users/{user_id}/inactivate
# ---------------------------------------------------------------------------


def test_inativar_usuario_sem_token_retorna_401():
    _use_fake_service()

    response = client.patch("/api/v1/users/42/inactivate")

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


def test_inativar_usuario_com_role_insuficiente_retorna_403():
    _use_fake_service()
    _authenticate_as("USER")

    response = client.patch("/api/v1/users/42/inactivate")

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_inativar_usuario_com_role_stock_keeper_retorna_403():
    _use_fake_service()
    _authenticate_as("STOCK_KEEPER")

    response = client.patch("/api/v1/users/42/inactivate")

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_inativar_usuario_com_sucesso_retorna_200():
    fake_user = _make_user(user_id=42, is_active=False, role_codes=["USER"])
    fake = _use_fake_service(user=fake_user)
    _authenticate_as("ADMINISTRATOR", user_id=99)

    response = client.patch("/api/v1/users/42/inactivate")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 42
    assert body["is_active"] is False
    assert fake.calls == [(42, 99)]


def test_inativar_usuario_inexistente_retorna_404():
    _use_fake_service(error=UserNotFoundError())
    _authenticate_as("ADMINISTRATOR")

    response = client.patch("/api/v1/users/9999/inactivate")

    assert response.status_code == 404
    assert response.json()["code"] == "user_not_found"


def test_inativar_usuario_ja_inativo_retorna_409():
    _use_fake_service(error=UserAlreadyInactiveError())
    _authenticate_as("ADMINISTRATOR")

    response = client.patch("/api/v1/users/42/inactivate")

    assert response.status_code == 409
    assert response.json()["code"] == "user_already_inactive"


def test_auto_inativacao_retorna_422():
    _use_fake_service(error=UserSelfInactivationError())
    _authenticate_as("ADMINISTRATOR", user_id=99)

    response = client.patch("/api/v1/users/99/inactivate")

    assert response.status_code == 422
    assert response.json()["code"] == "user_self_inactivation"


def test_usuario_inativo_nao_acessa_rota_protegida():
    """get_current_user deve rejeitar token de usuário inativo com 403."""
    inactive_user = _make_user(user_id=5, is_active=False, role_codes=["USER"])
    app.dependency_overrides[get_current_user] = lambda: (_ for _ in ()).throw(UserInactiveError())

    response = client.get("/api/v1/users/me")

    assert response.status_code == 403
    assert response.json()["code"] == "user_inactive"


# ---------------------------------------------------------------------------
# Service — UserService.inactivate_user
# ---------------------------------------------------------------------------


def _build_service(
    *,
    user: SimpleNamespace | None = None,
    session_error: bool = False,
):
    db = MagicMock()
    user_repo = MagicMock(spec=UserRepository)
    session_repo = MagicMock()
    service = UserService(db=db, user_repository=user_repo, session_repository=session_repo)
    return service, db, user_repo, session_repo


def test_service_auto_inativacao_lanca_erro():
    service, db, user_repo, session_repo = _build_service()

    with pytest.raises(UserSelfInactivationError):
        service.inactivate_user(7, actor_id=7)

    user_repo.find_by_id.assert_not_called()
    db.commit.assert_not_called()


def test_service_usuario_inexistente_lanca_not_found():
    service, db, user_repo, session_repo = _build_service()
    user_repo.find_by_id.return_value = None

    with pytest.raises(UserNotFoundError):
        service.inactivate_user(999, actor_id=1)

    db.commit.assert_not_called()


def test_service_usuario_ja_inativo_lanca_erro():
    service, db, user_repo, session_repo = _build_service()
    user_repo.find_by_id.return_value = _make_user(user_id=5, is_active=False)

    with pytest.raises(UserAlreadyInactiveError):
        service.inactivate_user(5, actor_id=1)

    db.commit.assert_not_called()


def test_service_inativacao_bem_sucedida_revoga_sessoes_e_persiste():
    service, db, user_repo, session_repo = _build_service()
    target = _make_user(user_id=10, is_active=True)
    user_repo.find_by_id.return_value = target
    user_repo.inactivate.return_value = _make_user(user_id=10, is_active=False)
    db.refresh.side_effect = lambda u: None

    service.inactivate_user(10, actor_id=1)

    session_repo.revoke_all_for_user.assert_called_once()
    revoke_args = session_repo.revoke_all_for_user.call_args
    assert revoke_args.args[0] == 10

    user_repo.inactivate.assert_called_once_with(10)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(target)


def test_service_ordem_operacoes_atomica():
    """Sessões devem ser revogadas ANTES do commit, garantindo atomicidade."""
    events: list[str] = []
    service, db, user_repo, session_repo = _build_service()
    target = _make_user(user_id=3, is_active=True)
    user_repo.find_by_id.return_value = target

    session_repo.revoke_all_for_user.side_effect = lambda *_: events.append("revoke")
    user_repo.inactivate.side_effect = lambda *_: events.append("inactivate")
    db.commit.side_effect = lambda: events.append("commit")

    service.inactivate_user(3, actor_id=1)

    assert events == ["revoke", "inactivate", "commit"]


# ---------------------------------------------------------------------------
# Repository — UserRepository.inactivate
# ---------------------------------------------------------------------------


def test_repository_inactivate_nao_controla_transacao():
    db = MagicMock()
    fake_user = MagicMock()
    fake_user.is_active = True
    db.get.return_value = fake_user
    repo = UserRepository(db)

    result = repo.inactivate(42)

    assert result is fake_user
    assert fake_user.is_active is False
    db.flush.assert_called_once()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_repository_inactivate_usuario_inexistente_retorna_none():
    db = MagicMock()
    db.get.return_value = None
    repo = UserRepository(db)

    result = repo.inactivate(9999)

    assert result is None
    db.flush.assert_not_called()


# ---------------------------------------------------------------------------
# Auth — bloqueio de login com usuário inativo
# ---------------------------------------------------------------------------


def test_login_com_usuario_inativo_retorna_401_sem_motivo_explicito():
    """O AuthService não deve vazar que a conta está inativa."""
    from app.services.auth_service import AuthService
    from app.core.exceptions import InvalidCredentialsError

    inactive_user = MagicMock()
    inactive_user.password_hash = "hash"
    inactive_user.is_active = False

    user_repo = MagicMock()
    user_repo.find_by_email.return_value = inactive_user

    service = AuthService(
        db=MagicMock(),
        user_repository=user_repo,
        session_repository=MagicMock(),
        role_repository=MagicMock(),
    )

    with patch("app.services.auth_service.verify_password", return_value=True):
        with pytest.raises(InvalidCredentialsError):
            service.login("inativo@example.com", "SenhaCorreta1!")


def test_get_current_user_com_usuario_inativo_lanca_user_inactive_error():
    """get_current_user deve lançar UserInactiveError para usuário inativo."""
    from app.dependencies.authentication import get_current_user as _get_current_user

    inactive_user = MagicMock()
    inactive_user.is_active = False

    mock_service = MagicMock()
    mock_service.get_by_id.return_value = inactive_user

    mock_creds = MagicMock()
    mock_creds.scheme = "bearer"
    mock_creds.credentials = "token"

    with patch("app.dependencies.authentication.decode_access_token", return_value=1):
        with pytest.raises(UserInactiveError):
            _get_current_user(credentials=mock_creds, user_service=mock_service)
