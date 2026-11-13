from datetime import datetime, timezone
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.controllers.notification_preference_controller import get_notification_preference_service
from app.core.exceptions import ApplicationError
from app.dependencies.authentication import get_current_user
from app.main import app
from app.models.domain import NotificationChannel as Channel
from app.repositories.notification_preference_repository import NotificationPreferenceRepository
from app.schemas.notification_preference_schema import NotificationPreferenceResponse, NotificationPreferenceUpdate
from app.services.notification_preference_service import NotificationPreferenceService

BASE = "/api/v1/me/notification-preferences"


@pytest.fixture
def api():
    service = Mock()
    service.get.return_value = service.update.return_value = NotificationPreferenceResponse(
        channel=Channel.IN_APP, email="client@example.com",
    )
    app.dependency_overrides[get_notification_preference_service] = lambda: service
    yield TestClient(app), service
    app.dependency_overrides.clear()


@pytest.mark.parametrize("method", ["get", "patch"])
def test_preferences_require_session_and_client_role(api, method):
    http, fake = api
    kwargs = {"json": {"channel": "EMAIL"}} if method == "patch" else {}
    assert getattr(http, method)(BASE, **kwargs).status_code == 401
    for role in ("SELLER", "STOCK_KEEPER", "ADMINISTRATOR"):
        app.dependency_overrides[get_current_user] = lambda role=role: NS(id=7, role_codes=[role])
        assert getattr(http, method)(BASE, **kwargs).status_code == 403
    fake.get.assert_not_called()
    fake.update.assert_not_called()


def test_preferences_use_authenticated_identity(api):
    http, fake = api
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=["USER"])
    response = http.get(BASE + "?user_id=999")
    assert response.status_code == 200
    assert response.json() == {"channel": "IN_APP", "email": "client@example.com"}
    fake.get.assert_called_once_with(7)
    assert http.patch(BASE, json={"channel": "IN_APP"}).status_code == 200
    assert fake.update.call_args.args == (7, NotificationPreferenceUpdate(channel="IN_APP"))


@pytest.mark.parametrize("payload", [{}, {"channel": None}, {"channel": "SMS"},
    {"channel": "EMAIL", "email": "other@example.com"}, {"channel": "IN_APP", "user_id": 8}])
def test_preferences_reject_invalid_channel_and_identity_fields(api, payload):
    http, fake = api
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=["USER"])
    response = http.patch(BASE, json=payload)
    assert response.status_code == 422 and response.json()["code"] == "validation_error"
    fake.update.assert_not_called()


@pytest.fixture
def service():
    db, repository = Mock(), Mock()
    profile = NS(id=7, is_active=True, notification_preference=Channel.IN_APP)
    user = NS(id=7, is_active=True, email="client@example.com")
    repository.find_client.return_value = (profile, user)
    repository.update.side_effect = lambda profile, channel, now: setattr(profile, "notification_preference", channel)
    return NotificationPreferenceService(db, repository), db, repository, profile, user


def test_service_updates_locked_profile_before_returning_persisted_result(service):
    target, db, repo, _, _ = service
    result = target.update(7, NotificationPreferenceUpdate(channel="EMAIL"))
    assert result.channel == Channel.EMAIL
    repo.find_client.assert_called_once_with(7, lock=True)
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


@pytest.mark.parametrize("condition,code", [("missing", "client_required"),
    ("profile_inactive", "client_inactive"), ("user_inactive", "client_inactive")])
@pytest.mark.parametrize("operation", ["get", "update"])
def test_service_rejects_missing_or_inactive_client(service, condition, code, operation):
    target, db, repo, profile, user = service
    if condition == "missing":
        repo.find_client.return_value = None
    elif condition == "profile_inactive":
        profile.is_active = False
    else:
        user.is_active = False
    args = (7,) if operation == "get" else (7, NotificationPreferenceUpdate(channel="EMAIL"))
    with pytest.raises(ApplicationError) as error:
        getattr(target, operation)(*args)
    assert error.value.status_code == 403 and error.value.code == code
    db.commit.assert_not_called()
    repo.update.assert_not_called()
    if operation == "update":
        db.rollback.assert_called_once()


def test_commit_failure_rolls_back_and_returns_stable_error(service):
    target, db, _, _, _ = service
    db.commit.side_effect = SQLAlchemyError("sensitive database information")
    with pytest.raises(ApplicationError) as error:
        target.update(7, NotificationPreferenceUpdate(channel="EMAIL"))
    assert (error.value.status_code, error.value.code) == (500, "notification_preference_persistence_error")
    assert "sensitive" not in error.value.message
    db.rollback.assert_called_once()


def test_repository_updates_only_channel_and_records_client_actor():
    db = Mock()
    repo = NotificationPreferenceRepository(db)
    profile = NS(id=7, notification_preference=Channel.IN_APP)
    now = datetime.now(timezone.utc)
    repo.update(profile, Channel.EMAIL, now)
    assert profile.notification_preference == Channel.EMAIL and profile.updated_at == now
    audit = db.add.call_args.args[0]
    assert audit.employee_id is None
    assert audit.new_value == {"channel": "EMAIL", "actor_user_id": 7}
    assert audit.old_value == {"channel": "IN_APP"}
    db.commit.assert_not_called()


def test_repository_same_channel_is_noop():
    db = Mock()
    repo = NotificationPreferenceRepository(db)
    profile = NS(id=7, notification_preference=Channel.IN_APP)
    repo.update(profile, Channel.IN_APP, datetime.now(timezone.utc))
    db.add.assert_not_called()
