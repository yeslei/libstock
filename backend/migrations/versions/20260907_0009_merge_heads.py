"""Consolida as heads de inativação de usuário e tags de destinação.

Revision ID: 20260907_0009
Revises: 20260906_0008, 20260907_0008
"""
from collections.abc import Sequence


revision: str = "20260907_0009"
down_revision: tuple[str, str] = ("20260906_0008", "20260907_0008")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge-only revision; both parent migrations already apply the changes."""


def downgrade() -> None:
    """Return to the two independent parent heads."""
