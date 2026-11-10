import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.models.domain import AuditLog, Client, NotificationChannel, Profile
from app.models.user import User
from app.repositories.notification_preference_repository import NotificationPreferenceRepository
from app.schemas.notification_preference_schema import NotificationPreferenceUpdate
from app.services.notification_preference_service import NotificationPreferenceService
from test_client_requests_postgres import records


def test_preferences_persist_and_audit_authenticated_client(records):
    engine, _, client_id = records
    with Session(engine) as db:
        service = NotificationPreferenceService(db, NotificationPreferenceRepository(db))
        assert service.get(client_id).channel == NotificationChannel.IN_APP
        service.update(client_id, NotificationPreferenceUpdate(channel="EMAIL"))
    with Session(engine) as db:
        assert db.get(Profile, client_id).notification_preference == NotificationChannel.EMAIL
        audit = db.scalar(select(AuditLog).where(AuditLog.entity_id == str(client_id),
            AuditLog.operation == "NOTIFICATION_PREFERENCE_CHANGED"))
        assert audit.new_value["actor_user_id"] == client_id
        # A penalidade é irrelevante para preferências de comunicação.
        db.get(Client, client_id).is_penalized = True
        db.commit()
        service = NotificationPreferenceService(db, NotificationPreferenceRepository(db))
        assert service.update(client_id, NotificationPreferenceUpdate(channel="IN_APP")).channel == NotificationChannel.IN_APP


def test_preferences_failed_commit_does_not_change_database(records):
    engine, _, client_id = records

    class FailedCommitSession(Session):
        def commit(self):
            self.flush()
            raise SQLAlchemyError("forced failure")

    with FailedCommitSession(engine) as db:
        service = NotificationPreferenceService(db, NotificationPreferenceRepository(db))
        with pytest.raises(ApplicationError) as error:
            service.update(client_id, NotificationPreferenceUpdate(channel="EMAIL"))
        assert error.value.code == "notification_preference_persistence_error"
    with Session(engine) as db:
        assert db.get(Profile, client_id).notification_preference == NotificationChannel.IN_APP
        assert db.scalar(select(AuditLog.id).where(AuditLog.entity_id == str(client_id),
            AuditLog.operation == "NOTIFICATION_PREFERENCE_CHANGED")) is None


def test_preloaded_authenticated_user_is_rechecked_after_concurrent_inactivation(records):
    engine, _, client_id = records
    with Session(engine) as authenticated:
        # Simula get_current_user populando o identity map antes do service.
        user = authenticated.get(User, client_id)
        assert user.is_active
        with Session(engine) as administrator:
            administrator.get(User, client_id).is_active = False
            administrator.commit()
        service = NotificationPreferenceService(authenticated, NotificationPreferenceRepository(authenticated))
        with pytest.raises(ApplicationError) as error:
            service.update(client_id, NotificationPreferenceUpdate(channel="EMAIL"))
        assert error.value.code == "client_inactive"
    with Session(engine) as db:
        assert db.get(Profile, client_id).notification_preference == NotificationChannel.IN_APP
