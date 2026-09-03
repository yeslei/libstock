from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from app.models.domain import Client, Profile, UserRole
from app.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_by_email(self, email: str) -> User | None:
        statement = (
            select(User)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .where(func.lower(User.email) == email.lower())
        )
        return self.db.scalar(statement)

    def find_by_id(self, user_id: int) -> User | None:
        statement = (
            select(User)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .where(User.id == user_id)
        )
        return self.db.scalar(statement)

    def create(
        self,
        *,
        name: str,
        email: str,
        password_hash: str,
    ) -> User:
        user = User(
            name=name,
            email=email,
            password_hash=password_hash,
        )
        self.db.add(user)
        self.db.flush()
        # Cadastros públicos são clientes. Funcionários são criados por um
        # fluxo administrativo separado.
        self.db.add(Profile(id=user.id))
        self.db.flush()
        self.db.add(Client(id=user.id))
        self.db.refresh(user)
        return user
