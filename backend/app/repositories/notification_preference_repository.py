from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import AuditLog, Client, NotificationChannel, Profile
from app.models.user import User


class NotificationPreferenceRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_client(self, user_id: int, *, lock: bool = False):
        query = (
            select(Profile, User)
            .join(User, User.id == Profile.id)
            .join(Client, Client.id == Profile.id)
            .where(Profile.id == user_id)
        )
        if lock:
            # Autenticação pode ter carregado User na mesma Session: reavaliar
            # atividade e preferência a partir das linhas efetivamente travadas.
            query = query.with_for_update().execution_options(populate_existing=True)
        return self.db.execute(query).first()

    def update(self, profile: Profile, channel: NotificationChannel, now: datetime) -> None:
        previous = profile.notification_preference
        if previous == channel:
            return
        profile.notification_preference = channel
        profile.updated_at = now
        self.db.add(AuditLog(
            entity_type="profiles", entity_id=str(profile.id),
            operation="NOTIFICATION_PREFERENCE_CHANGED",
            old_value={"channel": previous.value},
            new_value={"channel": channel.value, "actor_user_id": profile.id},
        ))
