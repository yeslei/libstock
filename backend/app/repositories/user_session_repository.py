from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.user_session import UserSession


class UserSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        refresh_token_hash: str,
        token_family: UUID,
        expires_at: datetime,
    ) -> UserSession:
        session = UserSession(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            token_family=token_family,
            expires_at=expires_at,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def find_by_hash_for_update(self, token_hash: str) -> UserSession | None:
        statement = (
            select(UserSession)
            .where(UserSession.refresh_token_hash == token_hash)
            .with_for_update()
        )
        return self.db.scalar(statement)

    def revoke_family(self, token_family: UUID, revoked_at: datetime) -> None:
        statement = (
            update(UserSession)
            .where(
                UserSession.token_family == token_family,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        self.db.execute(statement)
    def revoke_all_for_user(self, user_id: int, revoked_at: datetime) -> None:
        statement = (
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        self.db.execute(statement)
