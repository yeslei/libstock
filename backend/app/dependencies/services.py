from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.book_repository import BookRepository
from app.repositories.catalog_repository import CatalogRepository, GenreRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.repositories.user_session_repository import UserSessionRepository
from app.services.auth_service import AuthService
from app.services.book_service import BookService
from app.services.catalog_service import CatalogService
from app.services.user_service import UserService


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(
        db=db,
        user_repository=UserRepository(db),
        session_repository=UserSessionRepository(db),
        role_repository=RoleRepository(db),
    )


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(UserRepository(db))


def get_book_service(db: Session = Depends(get_db)) -> BookService:
    return BookService(db=db, repository=BookRepository(db))


def get_catalog_service(db: Session = Depends(get_db)) -> CatalogService:
    return CatalogService(
        db=db,
        catalog_repository=CatalogRepository(db),
        genre_repository=GenreRepository(db),
    )
