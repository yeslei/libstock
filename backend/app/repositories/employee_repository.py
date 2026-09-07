from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidEmployeeRoleError
from app.core.security import hash_password
from app.models.domain import Employee, Profile, Role, UserRole
from app.models.user import User
from app.schemas.employee_schema import EmployeeCreate, VALID_ROLE_CODES


@dataclass
class EmployeeCreated:
    id: int
    name: str
    email: str
    role_code: str


class EmployeeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data_in: EmployeeCreate) -> EmployeeCreated:
        role_code = data_in.accessLevel
        if role_code not in VALID_ROLE_CODES:
            raise InvalidEmployeeRoleError()

        role = self.db.scalar(select(Role).where(Role.code == role_code))
        if role is None:
            raise InvalidEmployeeRoleError()

        user = User(
            name=data_in.name,
            email=str(data_in.email).strip().lower(),
            password_hash=hash_password(data_in.password),
        )
        self.db.add(user)
        self.db.flush()

        self.db.add(Profile(id=user.id))
        self.db.flush()

        self.db.add(
            Employee(
                id=user.id,
                employee_code=f"EMP-{uuid4().hex[:12].upper()}",
                role_id=role.id,
            )
        )
        self.db.add(UserRole(user_id=user.id, role_id=role.id))
        self.db.flush()

        return EmployeeCreated(
            id=user.id,
            name=user.name,
            email=user.email,
            role_code=role.code,
        )