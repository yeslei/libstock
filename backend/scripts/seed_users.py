"""Cria contas de desenvolvimento para testar a API autenticada.

Uso, a partir de backend/:
    python scripts/seed_users.py
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.domain import Employee, Profile, Role, UserRole
from app.models.user import User


SEED_PASSWORD = "LibStock@2026"


@dataclass(frozen=True)
class SeedUser:
    name: str
    email: str
    role_code: str
    employee_code: str | None = None


USERS = (
    SeedUser("Cliente LibStock", "cliente@libstock.com.br", "USER"),
    SeedUser("Vendedor LibStock", "vendedor@libstock.com.br", "SELLER", "EMP-001"),
    SeedUser(
        "Estoquista LibStock",
        "estoquista@libstock.com.br",
        "STOCK_KEEPER",
        "EMP-002",
    ),
    SeedUser(
        "Administrador LibStock",
        "admin@libstock.com.br",
        "ADMINISTRATOR",
        "EMP-003",
    ),
)


def seed_users() -> None:
    with SessionLocal.begin() as db:
        password_hash = hash_password(SEED_PASSWORD)

        for seed_user in USERS:
            user = db.scalar(select(User).where(User.email == seed_user.email))
            if user is None:
                user = User(
                    name=seed_user.name,
                    email=seed_user.email,
                    password_hash=password_hash,
                )
                db.add(user)
                db.flush()

            role = db.scalar(select(Role).where(Role.code == seed_user.role_code))
            if role is None:
                raise RuntimeError(
                    f"Role {seed_user.role_code!r} não encontrada. "
                    "Execute 'alembic upgrade head' antes do seed."
                )

            user_role = db.get(UserRole, (user.id, role.id))
            if user_role is None:
                db.add(UserRole(user_id=user.id, role_id=role.id))

            if seed_user.employee_code is not None:
                profile = db.get(Profile, user.id)
                if profile is None:
                    db.add(Profile(id=user.id))
                    db.flush()

                employee = db.get(Employee, user.id)
                if employee is None:
                    db.add(
                        Employee(
                            id=user.id,
                            employee_code=seed_user.employee_code,
                            role_id=role.id,
                        )
                    )

    print("Usuários de desenvolvimento inseridos ou atualizados com sucesso.")


if __name__ == "__main__":
    seed_users()
