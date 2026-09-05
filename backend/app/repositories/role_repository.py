from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Role, UserRole


class RoleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_by_code(self, code: str) -> Role | None:
        statement = select(Role).where(Role.code == code)
        return self.db.scalar(statement)

    def assign_to_user(self, *, user_id: int, role_code: str) -> UserRole:
        role = self.find_by_code(role_code)
        if role is None:
            raise RuntimeError(f"Perfil obrigatório não encontrado: {role_code}")

        user_role = UserRole(user_id=user_id, role_id=role.id)
        self.db.add(user_role)
        self.db.flush()
        return user_role
