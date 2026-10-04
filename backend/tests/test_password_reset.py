"""Issue #154: HTTP contract, authorization, secrets and atomic orchestration."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import ApplicationError, InactiveUserError, PermissionDeniedError, UserNotFoundError
from app.core.security import verify_password
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_user_service
from app.main import app
from app.repositories.user_repository import UserRepository
from app.repositories.user_session_repository import UserSessionRepository
from app.schemas.user_schema import UserPasswordReset, UserPasswordResetResponse
from app.services.user_service import UserService

URL = '/api/v1/users/7/reset-password'
PASSWORD = 'nova-senha-teste'


@pytest.fixture(autouse=True)
def overrides():
    yield
    app.dependency_overrides.clear()


def http_setup(role='ADMINISTRATOR'):
    actor = SimpleNamespace(id=99, role_codes=[role], is_active=True)
    app.dependency_overrides[get_current_user] = lambda: actor
    service = MagicMock(spec=UserService)
    service.reset_password.return_value = UserPasswordResetResponse(user_id=7, message='Senha redefinida com sucesso.')
    app.dependency_overrides[get_user_service] = lambda: service
    return TestClient(app), service


def service_setup():
    db = MagicMock()
    users = MagicMock(spec=UserRepository)
    sessions = MagicMock(spec=UserSessionRepository)
    users.is_active_administrator_employee.return_value = True
    user = SimpleNamespace(id=7, is_active=False, password_hash='old')
    users.find_by_id_for_update.return_value = user
    return UserService(db, users, sessions), db, users, sessions, user


def test_http_success_never_returns_credentials_and_passes_actor():
    http, service = http_setup()
    response = http.post(URL, json={'new_password': PASSWORD})
    assert response.status_code == 200
    assert set(response.json()) == {'user_id', 'message'}
    assert PASSWORD not in response.text
    target, data = service.reset_password.call_args.args
    assert target == 7 and data.new_password.get_secret_value() == PASSWORD
    assert service.reset_password.call_args.kwargs == {'actor_id': 99}


@pytest.mark.parametrize('payload', [{}, {'new_password': 'short'}, {'new_password': 'x' * 129},
                                   {'new_password': None}, {'new_password': PASSWORD, 'password_hash': PASSWORD}])
def test_invalid_input_is_422_without_reflecting_any_input(payload):
    http, service = http_setup()
    response = http.post(URL, json=payload)
    assert response.status_code == 422
    for error in response.json()['detail']:
        assert 'input' not in error and 'ctx' not in error
    assert PASSWORD not in response.text
    service.reset_password.assert_not_called()


def test_unknown_field_name_cannot_reflect_a_secret():
    http, service = http_setup()
    response = http.post(URL, json={'new_password': PASSWORD, PASSWORD: 'ignored'})
    assert response.status_code == 422
    assert PASSWORD not in response.text
    extra = next(error for error in response.json()['detail'] if error['type'] == 'extra_forbidden')
    assert extra['loc'] == ['body', 'campo_desconhecido']
    service.reset_password.assert_not_called()


@pytest.mark.parametrize('target', [0, -1, 2**31, 'invalid'])
def test_invalid_id_never_calls_service(target):
    http, service = http_setup()
    assert http.post(f'/api/v1/users/{target}/reset-password', json={'new_password': PASSWORD}).status_code == 422
    service.reset_password.assert_not_called()


@pytest.mark.parametrize('role', ['USER', 'SELLER', 'STOCK_KEEPER'])
def test_only_administrator_is_authorized(role):
    http, service = http_setup(role)
    assert http.post(URL, json={'new_password': PASSWORD}).status_code == 403
    service.reset_password.assert_not_called()


def test_no_authentication_is_401():
    assert TestClient(app).post(URL, json={'new_password': PASSWORD}).status_code == 401


@pytest.mark.parametrize('inactive_profile', [False, True])
def test_real_authentication_dependency_rejects_inactive_actor(inactive_profile):
    http, service = http_setup()
    del app.dependency_overrides[get_current_user]
    service.get_by_id.return_value = SimpleNamespace(id=99, role_codes=['ADMINISTRATOR'], is_active=False)
    if inactive_profile:
        service.get_by_id.side_effect = InactiveUserError()
    with patch('app.dependencies.authentication.decode_access_token', return_value=99):
        response = http.post(URL, headers={'Authorization': 'Bearer test'}, json={'new_password': PASSWORD})
    assert response.status_code == 403
    service.reset_password.assert_not_called()


@pytest.mark.parametrize('error,code,status', [(UserNotFoundError(), 'user_not_found', 404),
                                             (PermissionDeniedError(), 'permission_denied', 403),
                                             (ApplicationError('Falha.', 'password_reset_persistence_error', 500),
                                              'password_reset_persistence_error', 500)])
def test_http_domain_errors(error, code, status):
    http, service = http_setup()
    service.reset_password.side_effect = error
    response = http.post(URL, json={'new_password': PASSWORD})
    assert (response.status_code, response.json()['code']) == (status, code)
    assert PASSWORD not in response.text


def test_service_hashes_revokes_audits_and_commits_in_order_without_changing_status():
    service, db, users, sessions, user = service_setup()
    ordered = MagicMock()
    ordered.attach_mock(users, 'users'); ordered.attach_mock(sessions, 'sessions'); ordered.attach_mock(db, 'db')
    result = service.reset_password(7, UserPasswordReset(new_password=PASSWORD), actor_id=99)
    _, password_hash, now = users.reset_password.call_args.args
    assert password_hash != PASSWORD and verify_password(PASSWORD, password_hash)
    assert user.is_active is False
    sessions.revoke_all_for_user.assert_called_once_with(7, now)
    users.audit_password_reset.assert_called_once_with(7, 99)
    names = [call[0] for call in ordered.mock_calls]
    assert names.index('users.find_by_id_for_update') < names.index('users.reset_password')
    assert names.index('users.reset_password') < names.index('sessions.revoke_all_for_user')
    assert names.index('sessions.revoke_all_for_user') < names.index('users.audit_password_reset') < names.index('db.commit')
    assert result.user_id == 7
    db.rollback.assert_not_called()


def test_inactive_non_employee_or_non_admin_actor_cannot_mutate():
    service, db, users, sessions, _ = service_setup()
    users.is_active_administrator_employee.return_value = False
    with pytest.raises(PermissionDeniedError):
        service.reset_password(7, UserPasswordReset(new_password=PASSWORD), actor_id=99)
    users.find_by_id_for_update.assert_not_called()
    sessions.revoke_all_for_user.assert_not_called()
    db.commit.assert_not_called(); db.rollback.assert_called_once()


def test_missing_target_is_404_without_mutation():
    service, db, users, sessions, _ = service_setup()
    users.find_by_id_for_update.return_value = None
    with pytest.raises(UserNotFoundError):
        service.reset_password(7, UserPasswordReset(new_password=PASSWORD), actor_id=99)
    users.reset_password.assert_not_called(); sessions.revoke_all_for_user.assert_not_called()
    db.commit.assert_not_called(); db.rollback.assert_called_once()


@pytest.mark.parametrize('where', ['password', 'sessions', 'audit', 'commit'])
def test_failure_at_each_persistence_step_rolls_back(where):
    service, db, users, sessions, _ = service_setup()
    operation = {'password': users.reset_password, 'sessions': sessions.revoke_all_for_user,
                 'audit': users.audit_password_reset, 'commit': db.commit}[where]
    operation.side_effect = SQLAlchemyError('forced failure')
    with pytest.raises(ApplicationError) as failure:
        service.reset_password(7, UserPasswordReset(new_password=PASSWORD), actor_id=99)
    assert failure.value.code == 'password_reset_persistence_error'
    db.rollback.assert_called_once()


def test_schema_repr_hides_password():
    assert PASSWORD not in repr(UserPasswordReset(new_password=PASSWORD))


def test_hashing_failure_rolls_back_before_any_mutation():
    service, db, users, sessions, _ = service_setup()
    with patch('app.services.user_service.hash_password', side_effect=RuntimeError('forced failure')):
        with pytest.raises(ApplicationError) as error:
            service.reset_password(7, UserPasswordReset(new_password=PASSWORD), actor_id=99)
    assert error.value.code == 'password_reset_persistence_error'
    users.reset_password.assert_not_called(); sessions.revoke_all_for_user.assert_not_called()
    db.rollback.assert_called_once()


def test_audit_repository_writes_identifiers_and_event_only():
    db = MagicMock()
    UserRepository(db).audit_password_reset(7, 99)
    event = db.add.call_args.args[0]
    assert (event.entity_type, event.entity_id, event.employee_id, event.operation) == ('users', '7', 99, 'PASSWORD_RESET')
    assert event.old_value is None and event.new_value is None
    db.flush.assert_called_once()
    db.commit.assert_not_called()
