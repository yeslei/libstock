"""Adiciona papéis de usuário e vínculos de autorização.

Revision ID: 20260903_0003
Revises: 20260902_0002
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260903_0003"
down_revision: str | None = "20260902_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("roles", sa.Column("code", sa.String(length=50), nullable=True))
    op.execute("UPDATE roles SET code = name WHERE code IS NULL")
    op.execute(
        """
        UPDATE roles
        SET name = 'Gerente',
            description = 'Responsável por gestão e operações administrativas'
        WHERE code = 'MANAGER'
        """
    )

    op.alter_column("roles", "code", nullable=False)
    op.create_unique_constraint("uq_roles_code", "roles", ["code"])

    op.execute(
        """
        INSERT INTO roles (code, name, description) VALUES
            ('USER', 'Usuário', 'Usuário comum do sistema'),
            ('SELLER', 'Vendedor', 'Responsável por operações de venda'),
            ('MANAGER', 'Gerente', 'Responsável por gestão e operações administrativas')
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description
        """
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])

    op.execute(
        """
        INSERT INTO user_roles (user_id, role_id)
        SELECT users.id, roles.id
        FROM users
        CROSS JOIN roles
        WHERE roles.code = 'USER'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_user_roles_role_id", table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_constraint("uq_roles_code", "roles", type_="unique")
    op.drop_column("roles", "code")
