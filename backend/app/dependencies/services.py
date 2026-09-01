from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.user_repository import UserRepository
from app.repositories.user_session_repository import UserSessionRepository
from app.services.auth_service import AuthService
from app.services.user_service import UserService


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(
        db=db,
        user_repository=UserRepository(db),
        session_repository=UserSessionRepository(db),
    )


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(UserRepository(db))
