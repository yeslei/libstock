from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import (
    DuplicateEmailError,
    InactiveUserError,
    LastActiveAdministratorError,
    PersistenceError,
    UserAlreadyInactiveError,
    UserNotFoundError,
    UserSelfInactivationError,
    UserSelfRoleRemovalError,
)
from sqlalchemy.exc import IntegrityError
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.user_session_repository import UserSessionRepository
from app.schemas.user_schema import UserUpdate


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
        profile = self.user_repository.find_profile_by_user_id(user_id)
        if profile is not None and not profile.is_active:
            raise InactiveUserError()
        return user

    def list_users(self, role_code: str | None = None) -> list[User]:
        return self.user_repository.list_all(role_code)

    def get_admin_user(self, user_id: int) -> User:
        user = self.user_repository.find_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        return user

    def update_user(self, target_id: int, data: UserUpdate, *, actor_id: int) -> User:
        user = self.user_repository.find_by_id(target_id)
        if user is None:
            raise UserNotFoundError()

        new_role = data.role_code
        removes_administrator = (
            "ADMINISTRATOR" in user.role_codes
            and new_role is not None
            and new_role != "ADMINISTRATOR"
        )
        if target_id == actor_id and removes_administrator:
            raise UserSelfRoleRemovalError()

        try:
            if removes_administrator:
                if self.user_repository.count_active_administrators_for_update() <= 1:
                    raise LastActiveAdministratorError()

            email = str(data.email).strip().lower() if data.email is not None else None
            self.user_repository.update(user, name=data.name, email=email)
            if new_role is not None and user.role_codes != [new_role]:
                self.user_repository.replace_role(user, new_role)
            self.db.commit()
            self.db.refresh(user)
            return user
        except (LastActiveAdministratorError, UserSelfRoleRemovalError):
            self.db.rollback()
            raise
        except IntegrityError as exc:
            self.db.rollback()
            constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            if constraint in ("ix_users_email", "uq_users_email", "users_email_key"):
                raise DuplicateEmailError() from exc
            raise PersistenceError() from exc
        except Exception as exc:
            self.db.rollback()
            if isinstance(exc, RuntimeError):
                raise PersistenceError() from exc
            raise


    def inactivate_user(self, target_id: int, *, actor_id: int) -> User:
        if target_id == actor_id:
            raise UserSelfInactivationError()

        user = self.user_repository.find_by_id(target_id)
        if user is None:
            raise UserNotFoundError()

        if not user.is_active:
            raise UserAlreadyInactiveError()

        if "ADMINISTRATOR" in user.role_codes:
            if self.user_repository.count_active_administrators_for_update() <= 1:
                self.db.rollback()
                raise LastActiveAdministratorError()

        try:
            # Revogar todas as sessões ativas atomicamente junto à inativação.
            self.session_repository.revoke_all_for_user(
                target_id,
                datetime.now(timezone.utc),
            )
            self.user_repository.inactivate(target_id)
            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception:
            self.db.rollback()
            raise
