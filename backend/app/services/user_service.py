from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import (
    UserAlreadyInactiveError,
    UserNotFoundError,
    UserSelfInactivationError,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.user_session_repository import UserSessionRepository


class UserService:
    def __init__(
        self,
        db: Session,
        user_repository: UserRepository,
        session_repository: UserSessionRepository,
    ) -> None:
        self.db = db
        self.user_repository = user_repository
        self.session_repository = session_repository

    def get_by_id(self, user_id: int) -> User:
        user = self.user_repository.find_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        return user

    def inactivate_user(self, target_id: int, *, actor_id: int) -> User:
        if target_id == actor_id:
            raise UserSelfInactivationError()

        user = self.user_repository.find_by_id(target_id)
        if user is None:
            raise UserNotFoundError()

        if not user.is_active:
            raise UserAlreadyInactiveError()

        # Revogar todas as sessões ativas atomicamente junto à inativação.
        self.session_repository.revoke_all_for_user(
            target_id,
            datetime.now(timezone.utc),
        )
        self.user_repository.inactivate(target_id)
        self.db.commit()
        self.db.refresh(user)
        return user
