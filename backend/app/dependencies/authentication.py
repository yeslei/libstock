from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import InvalidTokenError, UserNotFoundError
from app.core.security import decode_access_token
from app.models.user import User
from app.services.user_service import UserService

from app.dependencies.services import get_user_service


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    user_service: UserService = Depends(get_user_service),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise InvalidTokenError("Token de acesso não informado.")
    user_id = decode_access_token(credentials.credentials)
    try:
        return user_service.get_by_id(user_id)
    except UserNotFoundError as exc:
        raise InvalidTokenError() from exc
