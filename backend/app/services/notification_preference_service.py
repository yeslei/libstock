from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import ApplicationError
from app.repositories.notification_preference_repository import NotificationPreferenceRepository
from app.schemas.notification_preference_schema import (
    NotificationPreferenceResponse, NotificationPreferenceUpdate,
)


class NotificationPreferenceService:
    def __init__(self, db, repository: NotificationPreferenceRepository):
        self.db = db
        self.repository = repository

    def _client(self, user_id: int, *, lock: bool = False):
        records = self.repository.find_client(user_id, lock=lock)
        if records is None:
            raise ApplicationError("É necessário um cadastro de cliente.", "client_required", 403)
        profile, user = records
        if not profile.is_active or not user.is_active:
            raise ApplicationError("Cadastro de cliente inativo.", "client_inactive", 403)
        return profile, user

    def get(self, user_id: int) -> NotificationPreferenceResponse:
        try:
            profile, user = self._client(user_id)
            return NotificationPreferenceResponse(channel=profile.notification_preference, email=user.email)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ApplicationError(
                "Não foi possível consultar a preferência de notificação.",
                "notification_preference_read_error", 500,
            ) from exc

    def update(self, user_id: int, data: NotificationPreferenceUpdate) -> NotificationPreferenceResponse:
        try:
            profile, user = self._client(user_id, lock=True)
            self.repository.update(profile, data.channel, datetime.now(timezone.utc))
            response = NotificationPreferenceResponse(channel=profile.notification_preference, email=user.email)
            self.db.commit()
            return response
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ApplicationError(
                "Não foi possível salvar a preferência de notificação.",
                "notification_preference_persistence_error", 500,
            ) from exc
        except ApplicationError:
            self.db.rollback()
            raise
