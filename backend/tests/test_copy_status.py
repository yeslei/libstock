from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.controllers.copy_controller import get_copy_service
from app.core.exceptions import (
    ActiveEmployeeRequiredError, CopyNotFoundError, CopyStateConflictError,
    CopyTransitionNotAllowedError, CopyUpdatePersistenceError,
)
from app.dependencies.authentication import get_current_user
from app.main import app
from app.models.domain import CopyStatus
from app.schemas.copy_schema import CopyStatusUpdate
from app.services.copy_service import CopyService

NOW = datetime(2026, 11, 11, tzinfo=timezone.utc)


def exemplar(status=CopyStatus.AVAILABLE):
    return SimpleNamespace(id=1, book_id=2, barcode='COPY-31', destination='DIDACTIC',
                           condition=None, sale_price=None, acquired_at=None,
                           is_active=True, status=status, updated_at=NOW)


def service_for(status=CopyStatus.AVAILABLE):
    repository = MagicMock()
    db = MagicMock()
    copy = exemplar(status)
    repository.is_active_employee.return_value = True
    repository.find_for_update.return_value = copy
    repository.has_circulation_commitment.return_value = False

    def update(item, target):
        item.status = target
        item.updated_at = NOW + timedelta(seconds=1)
    repository.update_status.side_effect = update
    return CopyService(repository, db), repository, db, copy


def changes(status='INACTIVE', expected=NOW):
    return CopyStatusUpdate(status=status, expected_updated_at=expected)


@pytest.mark.parametrize('origin', list(CopyStatus))
@pytest.mark.parametrize('target', list(CopyStatus))
def test_manual_transition_matrix(origin, target):
    service, repo, db, copy = service_for(origin)
    if origin in {CopyStatus.AVAILABLE, CopyStatus.INACTIVE} and target in {CopyStatus.AVAILABLE, CopyStatus.INACTIVE}:
        result = service.update_status(1, changes(target), actor_id=7)
        assert result.status == target
        assert result.is_active is True
        assert result.barcode == 'COPY-31'
        db.commit.assert_called_once()
        if origin == target:
            repo.update_status.assert_not_called()
            repo.set_audit_actor.assert_not_called()
        else:
            repo.set_audit_actor.assert_called_once_with(7)
            assert result.updated_at > NOW
    else:
        with pytest.raises(CopyTransitionNotAllowedError):
            service.update_status(1, changes(target), actor_id=7)
        repo.update_status.assert_not_called()
        db.rollback.assert_called_once()
        db.commit.assert_not_called()


@pytest.mark.parametrize('scenario,error', [
    ('employee', ActiveEmployeeRequiredError), ('missing', CopyNotFoundError),
    ('version', CopyStateConflictError), ('circulation', CopyTransitionNotAllowedError),
])
def test_rejected_update_rolls_back(scenario, error):
    service, repo, db, copy = service_for()
    if scenario == 'employee': repo.is_active_employee.return_value = False
    if scenario == 'missing': repo.find_for_update.return_value = None
    if scenario == 'version': copy.updated_at = NOW + timedelta(seconds=1)
    if scenario == 'circulation': repo.has_circulation_commitment.return_value = True
    with pytest.raises(error):
        service.update_status(1, changes(), actor_id=7)
    db.commit.assert_not_called()
    db.rollback.assert_called_once()
    repo.update_status.assert_not_called()


@pytest.mark.parametrize('stage', ['read', 'audit', 'flush', 'commit'])
def test_persistence_failure_is_not_success(stage):
    service, repo, db, _ = service_for()
    method = {'read': repo.find_for_update, 'audit': repo.set_audit_actor,
              'flush': repo.update_status, 'commit': db.commit}[stage]
    method.side_effect = SQLAlchemyError('failure')
    with pytest.raises(CopyUpdatePersistenceError):
        service.update_status(1, changes(), actor_id=7)
    db.rollback.assert_called_once()


@pytest.fixture
def api():
    service, repo, db, copy = service_for()
    app.dependency_overrides[get_copy_service] = lambda: service
    with TestClient(app) as client:
        yield client, repo, db
    app.dependency_overrides.clear()


def authenticate(role):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role_codes=[role])


def payload():
    return {'status': 'INACTIVE', 'expected_updated_at': NOW.isoformat()}


@pytest.mark.parametrize('role,code', [(None, 401), ('USER', 403), ('SELLER', 403), ('STOCK_KEEPER', 200), ('ADMINISTRATOR', 200)])
def test_http_authorization(api, role, code):
    client, repo, db = api
    if role: authenticate(role)
    response = client.patch('/api/v1/copies/1/status', json=payload())
    assert response.status_code == code
    if code == 200:
        assert response.json()['status'] == 'INACTIVE'
        assert response.json()['is_active'] is True
    else:
        repo.update_status.assert_not_called()


@pytest.mark.parametrize('body', [{}, {'status': 'INACTIVE'}, {**payload(), 'status': None},
    {**payload(), 'status': 'LOST'}, {**payload(), 'is_active': False},
    {**payload(), 'expected_updated_at': '2026-11-11T00:00:00'},
    {**payload(), 'expected_updated_at': 'invalid'}, {**payload(), 'actor_id': 8}])
def test_http_input_validation(api, body):
    client, repo, _ = api
    authenticate('STOCK_KEEPER')
    assert client.patch('/api/v1/copies/1/status', json=body).status_code == 422
    repo.update_status.assert_not_called()


@pytest.mark.parametrize('copy_id', ['0', '-1', 'abc'])
def test_http_invalid_id(api, copy_id):
    authenticate('STOCK_KEEPER')
    assert api[0].patch(f'/api/v1/copies/{copy_id}/status', json=payload()).status_code == 422


@pytest.mark.parametrize('scenario,status,code', [
    ('missing', 404, 'copy_not_found'), ('employee', 403, 'active_employee_required'),
    ('conflict', 409, 'copy_state_conflict'), ('transition', 409, 'copy_transition_not_allowed'),
    ('persistence', 500, 'copy_update_persistence_error'),
])
def test_http_stable_domain_errors(api, scenario, status, code):
    client, repo, db = api
    authenticate('STOCK_KEEPER')
    if scenario == 'missing': repo.find_for_update.return_value = None
    if scenario == 'employee': repo.is_active_employee.return_value = False
    if scenario == 'conflict': repo.find_for_update.return_value.updated_at += timedelta(seconds=1)
    if scenario == 'transition': repo.find_for_update.return_value.status = CopyStatus.BORROWED
    if scenario == 'persistence': db.commit.side_effect = SQLAlchemyError('commit failed')
    response = client.patch('/api/v1/copies/1/status', json=payload())
    assert response.status_code == status
    assert response.json()['code'] == code


def test_http_inactive_user_denied_by_authentication(api, monkeypatch):
    from app.dependencies import authentication
    from app.dependencies.services import get_user_service
    user_service = MagicMock()
    user_service.get_by_id.return_value = SimpleNamespace(id=7, is_active=False)
    app.dependency_overrides[get_user_service] = lambda: user_service
    monkeypatch.setattr(authentication, 'decode_access_token', lambda _: 7)
    response = api[0].patch('/api/v1/copies/1/status', json=payload(),
                            headers={'Authorization': 'Bearer test-token'})
    assert response.status_code == 403
    assert response.json()['code'] == 'user_inactive'
    api[1].update_status.assert_not_called()
