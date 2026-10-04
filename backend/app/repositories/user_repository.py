from datetime import datetime, timezone

from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from app.models.domain import AuditLog, Client, Employee, Profile, Role, UserRole
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

    def get_user_by_id(self, user_id: int) -> User | None:
        """Consulta um usuário por identificador, sem aplicar regra de negócio."""
        return self.find_by_id(user_id)

    def is_active_administrator_employee(self, actor_id: int) -> bool:
        statement = (
            select(Employee.id)
            .join(Profile, Profile.id == Employee.id)
            .join(User, User.id == Employee.id)
            .join(Role, Role.id == Employee.role_id)
            .join(UserRole, (UserRole.user_id == User.id) & (UserRole.role_id == Role.id))
            .where(Employee.id == actor_id, User.is_active.is_(True),
                   Profile.is_active.is_(True), Role.code == "ADMINISTRATOR")
        )
        return self.db.scalar(statement) is not None

    def find_by_id_for_update(self, user_id: int) -> User | None:
        return self.db.scalar(select(User).where(User.id == user_id)
                              .with_for_update().execution_options(populate_existing=True))

    def reset_password(self, user: User, password_hash: str, changed_at: datetime) -> None:
        user.password_hash = password_hash
        user.updated_at = changed_at
        self.db.flush()

    def audit_password_reset(self, target_id: int, actor_id: int) -> None:
        # Credentials and their hashes must never enter audit payloads.
        self.db.add(AuditLog(employee_id=actor_id, entity_type="users", entity_id=str(target_id),
                             operation="PASSWORD_RESET", old_value=None, new_value=None))
        self.db.flush()

    def list_all(self, role_code: str | None = None) -> list[User]:
        statement = select(User).options(
            selectinload(User.roles).selectinload(UserRole.role)
        )
        if role_code is not None:
            statement = statement.where(
                User.roles.any(UserRole.role.has(Role.code == role_code))
            )
        statement = statement.order_by(func.lower(User.name), User.id)
        return list(self.db.scalars(statement).all())

    def count_active_administrators_for_update(self) -> int:
        # O lock na linha do papel serializa operações concorrentes que possam
        # remover ou inativar o último administrador.
        role_id = self.db.scalar(
            select(Role.id)
            .where(Role.code == "ADMINISTRATOR")
            .with_for_update()
        )
        if role_id is None:
            return 0
        statement = (
            select(func.count(User.id))
            .join(UserRole, UserRole.user_id == User.id)
            .where(UserRole.role_id == role_id, User.is_active.is_(True))
        )
        return int(self.db.scalar(statement) or 0)

    def find_profile_by_user_id(self, user_id: int) -> Profile | None:
        statement = select(Profile).where(Profile.id == user_id)
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

    def inactivate(self, user_id: int) -> User | None:
        user = self.db.get(User, user_id)
        if user is None:
            return None
        user.is_active = False
        user.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return user

    def update(self, user: User, *, name: str | None, email: str | None) -> None:
        if name is not None:
            user.name = name
        if email is not None:
            user.email = email
        user.updated_at = datetime.now(timezone.utc)
        self.db.flush()

    def replace_role(self, user: User, role_code: str) -> None:
        role = self.db.scalar(select(Role).where(Role.code == role_code))
        if role is None:
            raise RuntimeError(f"Papel obrigatório não encontrado: {role_code}")

        employee = self.db.get(Employee, user.id)
        client = self.db.get(Client, user.id)

        if role_code == "USER":
            if employee is not None:
                self.db.delete(employee)
            if client is None:
                self.db.add(Client(id=user.id))
        else:
            if client is not None:
                self.db.delete(client)
            if employee is None:
                self.db.add(
                    Employee(
                        id=user.id,
                        employee_code=f"EMP-{uuid4().hex[:12].upper()}",
                        role_id=role.id,
                    )
                )
            else:
                employee.role_id = role.id

        self.db.execute(delete(UserRole).where(UserRole.user_id == user.id))
        self.db.add(UserRole(user_id=user.id, role_id=role.id))
        user.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        self.db.expire(user, ["roles"])
