from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidTokenError,
    RefreshTokenReuseError,
)
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expiration,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.user_session_repository import UserSessionRepository
from app.repositories.role_repository import RoleRepository
from app.schemas.user_schema import UserCreate


@dataclass
class AuthenticationResult:
    user: User
    access_token: str
    access_token_expires_in: int
    refresh_token: str


class AuthService:
    def __init__(
        self,
        db: Session,
        user_repository: UserRepository,
        session_repository: UserSessionRepository,
        role_repository: RoleRepository,
    ) -> None:
        self.db = db
        self.user_repository = user_repository
        self.session_repository = session_repository
        self.role_repository = role_repository

    def register(self, data: UserCreate) -> User:
        email = str(data.email).strip().lower()
        if self.user_repository.find_by_email(email) is not None:
            raise DuplicateEmailError()

        try:
            user = self.user_repository.create(
                name=data.name,
                email=email,
                password_hash=hash_password(data.password),
                account_type=data.account_type,
            )
            self.role_repository.assign_to_user(user_id=user.id, role_code="USER")
            self.db.commit()
            self.db.refresh(user)
            return user
        except IntegrityError as exc:
            self.db.rollback()
            raise DuplicateEmailError() from exc

    def login(self, email: str, password: str) -> AuthenticationResult:
        user = self.user_repository.find_by_email(email.strip().lower())
        password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
        password_is_valid = verify_password(password, password_hash)
        if user is None or not password_is_valid:
            raise InvalidCredentialsError()

        return self._create_session(user)

    def refresh(self, raw_refresh_token: str) -> AuthenticationResult:
        now = datetime.now(timezone.utc)
        token_hash = hash_refresh_token(raw_refresh_token)
        current_session = self.session_repository.find_by_hash_for_update(token_hash)
        if current_session is None:
            raise InvalidTokenError("Refresh token inválido.")

        if current_session.revoked_at is not None:
            self.session_repository.revoke_family(current_session.token_family, now)
            self.db.commit()
            raise RefreshTokenReuseError()

        expires_at = current_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            current_session.revoked_at = now
            self.db.commit()
            raise InvalidTokenError("Refresh token expirado.")

        user = current_session.user
        new_refresh_token = generate_refresh_token()
        new_session = self.session_repository.create(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(new_refresh_token),
            token_family=current_session.token_family,
            expires_at=refresh_token_expiration(),
        )
        current_session.revoked_at = now
        current_session.last_used_at = now
        current_session.replaced_by_id = new_session.id

        access_token, expires_in = create_access_token(user.id)
        self.db.commit()
        return AuthenticationResult(user, access_token, expires_in, new_refresh_token)

    def logout(self, raw_refresh_token: str | None) -> None:
        if not raw_refresh_token:
            return
        session = self.session_repository.find_by_hash_for_update(
            hash_refresh_token(raw_refresh_token)
        )
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            self.db.commit()

    def logout_all(self, user_id: int) -> None:
        self.session_repository.revoke_all_for_user(
            user_id,
            datetime.now(timezone.utc),
        )
        self.db.commit()

    def _create_session(self, user: User) -> AuthenticationResult:
        refresh_token = generate_refresh_token()
        self.session_repository.create(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(refresh_token),
            token_family=uuid4(),
            expires_at=refresh_token_expiration(),
        )
        access_token, expires_in = create_access_token(user.id)
        self.db.commit()
        return AuthenticationResult(user, access_token, expires_in, refresh_token)
