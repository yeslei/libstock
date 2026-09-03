"""Remove users.account_type e o enum account_type.

A distinção PF/PJ deixou de existir no domínio: o papel do usuário passa a ser
definido pelas roles (USER, SELLER, MANAGER, ...) e pela especialização
Client/Employee. A coluna não é mais escrita pelo cadastro nem exposta pela API.

Revision ID: 20260903_0004
Revises: 20260903_0003
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260903_0004"
down_revision: str | None = "20260903_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ACCOUNT_TYPE = sa.Enum("PF", "PJ", name="account_type")


def upgrade() -> None:
    op.drop_column("users", "account_type")
    ACCOUNT_TYPE.drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    ACCOUNT_TYPE.create(op.get_bind(), checkfirst=True)
    # Usuários criados após a remoção não têm tipo de conta; 'PF' é o padrão
    # assumido para que a coluna possa voltar a ser obrigatória.
    op.add_column(
        "users",
        sa.Column("account_type", ACCOUNT_TYPE, nullable=True),
    )
    op.execute("UPDATE users SET account_type = 'PF' WHERE account_type IS NULL")
    op.alter_column("users", "account_type", existing_type=ACCOUNT_TYPE, nullable=False)
