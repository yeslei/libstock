"""Consolida os papéis nos quatro perfis do SRS.

Revision ID: 20260905_0007
Revises: 20260905_0006
"""
from collections.abc import Sequence

from alembic import op


revision: str = "20260905_0007"
down_revision: str | None = "20260905_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# A tabela nasceu com seis códigos porque a 0002 e a 0003 semearam papéis sem
# conhecimento uma da outra. O SRS (seção 1.3) descreve quatro atores, e dois
# pares eram o mesmo ator escrito de duas formas.
FUSOES: tuple[tuple[str, str], ...] = (
    ("ATTENDANT", "SELLER"),        # "Atendentes de Caixa | Vendedores"
    ("MANAGER", "ADMINISTRATOR"),   # "Gerente | Dono: Administrador"
)

NOMES: tuple[tuple[str, str, str], ...] = (
    ("USER", "Cliente", "Cliente ou leitor que consulta o acervo"),
    ("SELLER", "Vendedor", "Atendente de caixa responsável pelas operações de balcão"),
    ("STOCK_KEEPER", "Estoquista", "Responsável pela organização e classificação do acervo"),
    ("ADMINISTRATOR", "Administrador", "Controle total das regras de negócio"),
)


# Recriada porque o corpo tem os códigos de papel gravados: MANAGER some, e a
# checagem de destinação passa a exigir apenas ADMINISTRATOR.
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
            RAISE EXCEPTION 'Only available or inactive copies can change destination';
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
                RAISE EXCEPTION '%(mensagem)s';
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
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("O domínio do LibStock requer PostgreSQL.")

    for origem, destino in FUSOES:
        # Quem já tivesse os dois papéis violaria a chave primária composta no
        # UPDATE, então esse vínculo redundante é removido antes.
        op.execute(
            f"""
            DELETE FROM user_roles ur
            USING roles origem, roles destino
            WHERE ur.role_id = origem.id
              AND origem.code = '{origem}'
              AND destino.code = '{destino}'
              AND EXISTS (
                  SELECT 1 FROM user_roles existente
                  WHERE existente.user_id = ur.user_id
                    AND existente.role_id = destino.id
              )
            """
        )
        op.execute(
            f"""
            UPDATE user_roles ur
            SET role_id = destino.id
            FROM roles origem, roles destino
            WHERE ur.role_id = origem.id
              AND origem.code = '{origem}'
              AND destino.code = '{destino}'
            """
        )
        op.execute(
            f"""
            UPDATE employees e
            SET role_id = destino.id
            FROM roles origem, roles destino
            WHERE e.role_id = origem.id
              AND origem.code = '{origem}'
              AND destino.code = '{destino}'
            """
        )

    op.execute(
        GUARD_COPY_INTEGRITY
        % {
            "papeis": "= 'ADMINISTRATOR'",
            "mensagem": "Changing destination requires an administrator",
        }
    )

    op.execute("DELETE FROM roles WHERE code IN ('ATTENDANT', 'MANAGER')")

    # Três papéis carregavam o próprio código como nome, porque a 0003 só
    # renomeou MANAGER. O nome é o que a interface exibe.
    for codigo, nome, descricao in NOMES:
        op.execute(
            f"""
            UPDATE roles SET name = '{nome}', description = '{descricao}'
            WHERE code = '{codigo}'
            """
        )


def downgrade() -> None:
    op.execute(
        """
        INSERT INTO roles (code, name, description) VALUES
            ('ATTENDANT', 'Atendente', 'Atendente das operações de balcão'),
            ('MANAGER', 'Gerente', 'Responsável por gestão e operações administrativas')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        GUARD_COPY_INTEGRITY
        % {
            "papeis": "IN ('MANAGER', 'ADMINISTRATOR')",
            "mensagem": "Changing destination requires a manager or administrator",
        }
    )
    op.execute(
        """
        UPDATE roles SET name = 'Usuário', description = 'Usuário comum do sistema'
        WHERE code = 'USER'
        """
    )
