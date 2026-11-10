from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.controllers.notification_controller import get_notification_service
from app.core.exceptions import ApplicationError
from app.dependencies.authentication import get_current_user
from app.main import app
from app.models.domain import NotificationChannel as Channel, NotificationStatus as Status, ReservationStatus
from app.schemas.notification_schema import NotificationPage
from app.services.notification_service import AVAILABILITY_EVENT, NotificationService


def notification(**overrides):
    values = dict(id=8, user_id=7, reservation_id=12, type=AVAILABILITY_EVENT, channel=Channel.IN_APP,
        subject="Disponível", message="Retire no balcão.", status=Status.SENT,
        created_at=datetime.now(timezone.utc), sent_at=datetime.now(timezone.utc), read_at=None)
    return NS(**(values | overrides))


@pytest.fixture
def service():
    db, repo, preferences = Mock(), Mock(), Mock()
    return NotificationService(db, repo, preferences), db, repo, preferences


@pytest.mark.parametrize("channel,status", [(Channel.IN_APP, Status.SENT), (Channel.EMAIL, Status.PENDING)])
def test_enqueue_uses_preference_and_never_sends_or_commits(service, channel, status):
    target, db, repo, _ = service
    reservation = NS(id=12, client_id=7, status=ReservationStatus.NOTIFIED,
        expires_at=datetime(2026, 11, 15, 2, 59, tzinfo=timezone.utc))
    repo.availability_data.return_value = (reservation, NS(title="Dom Casmurro"), NS(notification_preference=channel), NS())
    target.enqueue_availability(12)
    values = repo.enqueue.call_args.kwargs
    assert (values["user_id"], values["reservation_id"], values["type"]) == (7, 12, AVAILABILITY_EVENT)
    assert values["status"] == status
    assert (values["sent_at"] is not None) == (channel == Channel.IN_APP)
    assert "14/11/2026" in values["message"] and "Dom Casmurro" in values["message"]
    db.commit.assert_not_called()


def test_list_is_scoped_and_uses_cursor_without_exposing_personal_data(service):
    target, _, repo, preferences = service
    repo.list_own.return_value = [notification(id=8), notification(id=7), notification(id=6)]
    response = target.list_own(7, before_id=9, limit=2)
    preferences.get.assert_called_once_with(7)
    repo.list_own.assert_called_once_with(7, before_id=9, limit=3)
    assert [item.id for item in response.items] == [8, 7] and response.next_before_id == 7
    assert "user_id" not in response.items[0].model_dump()


def test_mark_read_is_owned_and_idempotent(service):
    target, db, repo, preferences = service
    item = notification()
    repo.lock_own.return_value = item
    response = target.mark_read(7, 8)
    assert response.status == Status.READ and response.read_at >= item.sent_at
    previous = response.read_at
    assert target.mark_read(7, 8).read_at == previous
    repo.lock_own.assert_called_with(8, 7)
    preferences._client.assert_called_with(7, lock=True)
    assert db.commit.call_count == 2


@pytest.mark.parametrize("state,code,status", [(None, "notification_not_found", 404),
    (Status.PENDING, "notification_not_delivered", 409), (Status.FAILED, "notification_not_delivered", 409)])
def test_read_never_exposes_other_users_or_fabricates_delivery(service, state, code, status):
    target, db, repo, _ = service
    repo.lock_own.return_value = None if state is None else notification(status=state, sent_at=None)
    with pytest.raises(ApplicationError) as error:
        target.mark_read(7, 8)
    assert (error.value.code, error.value.status_code) == (code, status)
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_read_failure_rolls_back(service):
    target, db, repo, _ = service
    repo.lock_own.return_value = notification()
    db.commit.side_effect = SQLAlchemyError("secret")
    with pytest.raises(ApplicationError) as error:
        target.mark_read(7, 8)
    assert error.value.code == "notification_persistence_error"
    db.rollback.assert_called_once()


@pytest.fixture
def api():
    fake = Mock()
    fake.list_own.return_value = NotificationPage(items=[], next_before_id=None)
    app.dependency_overrides[get_notification_service] = lambda: fake
    yield TestClient(app), fake
    app.dependency_overrides.clear()


def test_notifications_require_client_role_and_authenticated_identity(api):
    http, fake = api
    assert http.get("/api/v1/me/notifications").status_code == 401
    assert http.patch("/api/v1/me/notifications/8/read").status_code == 401
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=["SELLER"])
    assert http.get("/api/v1/me/notifications").status_code == 403
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=["USER"])
    response = http.get("/api/v1/me/notifications?user_id=999&limit=10&before_id=9")
    assert response.json() == {"items": [], "next_before_id": None}
    fake.list_own.assert_called_once_with(7, before_id=9, limit=10)


@pytest.mark.parametrize("path", ["?limit=0", "?limit=101", "?before_id=0", "/0/read"])
def test_notification_input_validation(api, path):
    http, _ = api
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=["USER"])
    response = http.patch("/api/v1/me/notifications" + path) if path.endswith("read") else http.get("/api/v1/me/notifications" + path)
    assert response.status_code == 422
