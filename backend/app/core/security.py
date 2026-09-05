import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from jwt import InvalidTokenError as PyJWTInvalidTokenError
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.exceptions import InvalidTokenError


password_hasher = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hasher.hash("libstock-dummy-password")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(user_id: int) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_in = settings.access_token_expire_minutes * 60
    payload = {
        "sub": str(user_id),
        "type": "access",
        "jti": str(uuid4()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_in


def decode_access_token(token: str) -> int:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "type", "jti", "iss", "aud", "iat", "exp"]},
        )
        if payload.get("type") != "access":
            raise InvalidTokenError()
        return int(payload["sub"])
    except (PyJWTInvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError() from exc


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expiration() -> datetime:
    settings = get_settings()
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
