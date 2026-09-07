"""Adiciona gêneros literários e destaque de catálogo.

Revision ID: 20260905_0006
Revises: 20260905_0005
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260905_0006"
down_revision: str | None = "20260905_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Gêneros exibidos na home. A ordem aqui define o display_order.
SEED_GENRES: tuple[tuple[str, str], ...] = (
    ("Ficção", "ficcao"),
    ("Não ficção", "nao-ficcao"),
    ("Romance", "romance"),
    ("Fantasia", "fantasia"),
    ("Suspense", "suspense"),
    ("Infantil", "infantil"),
    ("Biografia", "biografia"),
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("O domínio do LibStock requer PostgreSQL.")

    op.create_table(
        "genres",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column(
            "is_featured", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("display_order", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("idx_genres_featured", "genres", ["is_featured", "display_order"])

    # CASCADE nos dois lados: apagar livro ou gênero limpa o vínculo em vez de
    # travar. Difere do RESTRICT usado entre books e copies, onde o exemplar é
    # um registro de acervo que não pode sumir junto.
    op.create_table(
        "book_genres",
        sa.Column("book_id", sa.BigInteger(), nullable=False),
        sa.Column("genre_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["genre_id"], ["genres.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("book_id", "genre_id"),
    )
    # A PK composta já cobre buscas por book_id; o índice serve ao sentido
    # inverso, que é o da listagem "livros deste gênero".
    op.create_index("idx_book_genres_genre", "book_genres", ["genre_id"])

    op.add_column(
        "books",
        sa.Column(
            "is_featured", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.add_column("books", sa.Column("featured_position", sa.Integer(), nullable=True))
    op.create_index(
        "idx_books_featured",
        "books",
        ["featured_position"],
        postgresql_where=sa.text("is_featured"),
    )

    genres_table = sa.table(
        "genres",
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("is_featured", sa.Boolean),
        sa.column("display_order", sa.Integer),
    )
    op.execute(
        genres_table.insert().values(
            [
                {
                    "name": name,
                    "slug": slug,
                    "is_featured": True,
                    "display_order": position,
                }
                for position, (name, slug) in enumerate(SEED_GENRES, start=1)
            ]
        )
    )


def downgrade() -> None:
    op.drop_index("idx_books_featured", table_name="books")
    op.drop_column("books", "featured_position")
    op.drop_column("books", "is_featured")
    op.drop_index("idx_book_genres_genre", table_name="book_genres")
    op.drop_table("book_genres")
    op.drop_index("idx_genres_featured", table_name="genres")
    op.drop_table("genres")
