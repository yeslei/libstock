"""Adiciona tags de destinação ao acervo.

Revision ID: 20260907_0008
Revises: 20260905_0007
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260907_0008"
down_revision: str | None = "20260905_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SEED_DESTINATION_TAGS: tuple[tuple[str, str, str], ...] = (
    ("Doação", "doacao", "Itens destinados a doação para terceiros ou instituições"),
    ("Descarte", "descarte", "Itens danificados ou obsoletos destinados a descarte"),
    ("Venda", "venda", "Itens destinados à comercialização"),
    ("Acervo Fixo", "acervo-fixo", "Itens de consulta local ou patrimônio fixo"),
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("O domínio do LibStock requer PostgreSQL.")

    op.create_table(
        "destination_tags",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )

    tags_table = sa.table(
        "destination_tags",
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("description", sa.String),
    )
    op.execute(
        tags_table.insert().values(
            [
                {
                    "name": name,
                    "slug": slug,
                    "description": description,
                }
                for name, slug, description in SEED_DESTINATION_TAGS
            ]
        )
    )

    op.add_column(
        "copies",
        sa.Column("destination_tag_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_copies_destination_tag",
        "copies",
        "destination_tags",
        ["destination_tag_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_copies_destination_tag", "copies", ["destination_tag_id"])


def downgrade() -> None:
    op.drop_index("idx_copies_destination_tag", table_name="copies")
    op.drop_constraint("fk_copies_destination_tag", "copies", type_="foreignkey")
    op.drop_column("copies", "destination_tag_id")
    op.drop_table("destination_tags")

