"""Permite que vendedor e estoquista convertam a destinação de exemplar (Issue #151, decisão 6 de #147).

Revision ID: 20261003_0014
Revises: 20261003_0013
"""
from collections.abc import Sequence

from alembic import op


revision: str = "20261003_0014"
down_revision: str | None = "20261003_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Mesmo corpo de `guard_copy_integrity` da migration 20260905_0007; só a lista de papéis que
# podem trocar a destinação de um exemplar muda (antes, apenas ADMINISTRATOR).
GUARD_COPY_INTEGRITY = """
CREATE OR REPLACE FUNCTION guard_copy_integrity() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    actor_id integer;
BEGIN
    IF TG_OP = 'INSERT' AND NEW.status NOT IN ('AVAILABLE', 'INACTIVE') THEN
        RAISE EXCEPTION 'A new copy must start as AVAILABLE or INACTIVE';
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF NEW.destination IS DISTINCT FROM OLD.destination
           AND OLD.status NOT IN ('AVAILABLE', 'INACTIVE') THEN
            RAISE EXCEPTION 'Only available or inactive copies can change destination'%(errcode_not_available)s;
        END IF;

        IF NEW.destination IS DISTINCT FROM OLD.destination THEN
            actor_id := current_audit_employee_id();
            IF actor_id IS NULL OR NOT EXISTS (
                SELECT 1
                FROM user_roles ur
                JOIN roles r ON r.id = ur.role_id
                WHERE ur.user_id = actor_id
                  AND r.code %(papeis)s
            ) THEN
                RAISE EXCEPTION '%(mensagem)s'%(errcode_forbidden)s;
            END IF;
        END IF;

        IF NEW.status = 'BORROWED'
           AND NOT EXISTS (
               SELECT 1 FROM loans
               WHERE copy_id = NEW.id AND status = 'OPEN'
           ) THEN
            RAISE EXCEPTION 'BORROWED copy requires an open loan';
        END IF;

        IF NEW.status = 'SOLD'
           AND NOT EXISTS (
               SELECT 1
               FROM sale_items si
               JOIN sales s ON s.id = si.sale_id
               WHERE si.copy_id = NEW.id AND s.status = 'CONFIRMED'
           ) THEN
            RAISE EXCEPTION 'SOLD copy requires a confirmed sale';
        END IF;

        IF NEW.status IN ('AVAILABLE', 'RESERVED', 'INACTIVE')
           AND EXISTS (
               SELECT 1 FROM loans
               WHERE copy_id = NEW.id AND status = 'OPEN'
           ) THEN
            RAISE EXCEPTION 'An open loan requires the copy to remain BORROWED';
        END IF;

        IF NEW.status <> 'SOLD'
           AND EXISTS (
               SELECT 1
               FROM sale_items si
               JOIN sales s ON s.id = si.sale_id
               WHERE si.copy_id = NEW.id AND s.status = 'CONFIRMED'
           ) THEN
            RAISE EXCEPTION 'A copy in a confirmed sale must remain SOLD';
        END IF;

        IF NOT NEW.is_active
           AND EXISTS (
               SELECT 1 FROM loans
               WHERE copy_id = NEW.id AND status = 'OPEN'
           ) THEN
            RAISE EXCEPTION 'A borrowed copy cannot be deactivated';
        END IF;
    END IF;
    RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    op.execute(
        GUARD_COPY_INTEGRITY
        % {
            "papeis": "IN ('SELLER', 'STOCK_KEEPER', 'ADMINISTRATOR')",
            "mensagem": "Changing destination requires a seller, stock keeper or administrator",
            # SQLSTATE próprios (mapeados no service sem depender do texto da mensagem).
            "errcode_forbidden": " USING ERRCODE = 'LS001'",
            "errcode_not_available": " USING ERRCODE = 'LS002'",
        }
    )


def downgrade() -> None:
    op.execute(
        GUARD_COPY_INTEGRITY
        % {
            "papeis": "= 'ADMINISTRATOR'",
            "mensagem": "Changing destination requires an administrator",
            "errcode_forbidden": "",
            "errcode_not_available": "",
        }
    )
