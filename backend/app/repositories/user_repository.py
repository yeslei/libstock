from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import AccountType, User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_by_email(self, email: str) -> User | None:
        statement = select(User).where(func.lower(User.email) == email.lower())
        return self.db.scalar(statement)

    def find_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def create(
        self,
        *,
        name: str,
        email: str,
        password_hash: str,
        account_type: AccountType,
    ) -> User:
        user = User(
            name=name,
            email=email,
            password_hash=password_hash,
            account_type=account_type,
        )
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user
