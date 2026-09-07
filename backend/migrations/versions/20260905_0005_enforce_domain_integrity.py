"""Reforça as regras de integridade do domínio LibStock.

Revision ID: 20260905_0005
Revises: 20260903_0004
"""
from collections.abc import Sequence

from alembic import op


revision: str = "20260905_0005"
down_revision: str | None = "20260903_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("O domínio do LibStock requer PostgreSQL.")

    # Uma venda cancelada não pode impedir permanentemente uma venda futura.
    op.execute("ALTER TABLE sale_items DROP CONSTRAINT uq_sale_item_copy")

    op.execute(
        """
        ALTER TABLE copies ADD CONSTRAINT chk_didactic_without_sale_price
        CHECK (destination = 'COMMERCIAL' OR sale_price IS NULL)
        """
    )
    op.execute(
        """
        ALTER TABLE loans ADD CONSTRAINT chk_loan_status_dates
        CHECK (
            (status = 'OPEN' AND returned_at IS NULL)
            OR (status = 'RETURNED' AND returned_at IS NOT NULL)
            OR (status = 'CANCELLED' AND returned_at IS NULL)
        )
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY book_id ORDER BY requested_at, id
                   ) AS new_position
            FROM purchase_reservations
            WHERE status IN ('WAITING', 'NOTIFIED')
        )
        UPDATE purchase_reservations reservation
        SET queue_position = ranked.new_position
        FROM ranked
        WHERE reservation.id = ranked.id
        """
    )
    op.execute(
        """
        ALTER TABLE purchase_reservations
        ADD CONSTRAINT chk_reservation_state CHECK (
            (status = 'WAITING' AND queue_position IS NOT NULL
                AND notified_at IS NULL AND fulfilled_copy_id IS NULL)
            OR (status = 'NOTIFIED' AND queue_position IS NOT NULL
                AND notified_at IS NOT NULL AND fulfilled_copy_id IS NULL)
            OR (status = 'FULFILLED' AND fulfilled_copy_id IS NOT NULL)
            OR status IN ('CANCELLED', 'EXPIRED')
        )
        """
    )
    op.execute(
        """
        ALTER TABLE notifications ADD CONSTRAINT chk_notification_state CHECK (
            (status = 'PENDING' AND sent_at IS NULL AND read_at IS NULL)
            OR (status = 'SENT' AND sent_at IS NOT NULL AND read_at IS NULL)
            OR (status = 'READ' AND sent_at IS NOT NULL AND read_at IS NOT NULL
                AND read_at >= sent_at)
            OR (status = 'FAILED' AND read_at IS NULL)
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_active_reservation_book_queue
        ON purchase_reservations(book_id, queue_position)
        WHERE status IN ('WAITING', 'NOTIFIED')
        """
    )

    # Mantém timestamps de atualização corretos sem depender da aplicação.
    op.execute(
        """
        CREATE FUNCTION set_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$
        """
    )
    for table in ("profiles", "books", "copies"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
            """
        )

    # O funcionário da operação pode ser propagado por SET LOCAL
    # libstock.employee_id = '<id>'. Transições de empréstimo e venda fazem isso
    # automaticamente antes de alterar o exemplar.
    op.execute(
        """
        CREATE FUNCTION current_audit_employee_id() RETURNS integer
        LANGUAGE plpgsql STABLE AS $$
        DECLARE
            raw_value text;
            employee_value integer;
        BEGIN
            raw_value := current_setting('libstock.employee_id', true);
            IF raw_value IS NULL OR raw_value = '' THEN
                RETURN NULL;
            END IF;
            employee_value := raw_value::integer;
            IF NOT EXISTS (SELECT 1 FROM employees WHERE id = employee_value) THEN
                RAISE EXCEPTION 'Unknown audit employee id: %', employee_value;
            END IF;
            RETURN employee_value;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION audit_inventory_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            row_id text;
            employee_value integer;
        BEGIN
            employee_value := current_audit_employee_id();
            IF employee_value IS NULL THEN
                RAISE EXCEPTION
                    'Inventory changes require SET LOCAL libstock.employee_id';
            END IF;
            IF TG_OP = 'DELETE' THEN
                row_id := OLD.id::text;
            ELSE
                row_id := NEW.id::text;
            END IF;
            INSERT INTO audit_logs (
                employee_id, entity_type, entity_id, operation, old_value, new_value
            ) VALUES (
                employee_value,
                TG_TABLE_NAME,
                row_id,
                TG_OP,
                CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE to_jsonb(OLD) END,
                CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE to_jsonb(NEW) END
            );
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    for table in ("books", "copies"):
        op.execute(
            f"""
            CREATE TRIGGER trg_audit_{table}
            AFTER INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION audit_inventory_change()
            """
        )

    # Impede que status físicos sejam forjados sem a transação correspondente.
    op.execute(
        """
        CREATE FUNCTION guard_copy_integrity() RETURNS trigger
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
                          AND r.code IN ('MANAGER', 'ADMINISTRATOR')
                    ) THEN
                        RAISE EXCEPTION 'Changing destination requires a manager or administrator';
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
    )
    op.execute(
        """
        CREATE TRIGGER trg_guard_copy_integrity
        BEFORE INSERT OR UPDATE ON copies
        FOR EACH ROW EXECUTE FUNCTION guard_copy_integrity()
        """
    )

    # Empréstimos validam cliente e exemplar e controlam o estado físico.
    op.execute(
        """
        CREATE FUNCTION validate_loan() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            copy_record copies%ROWTYPE;
        BEGIN
            IF TG_OP = 'INSERT' AND NEW.status <> 'OPEN' THEN
                RAISE EXCEPTION 'A loan must start as OPEN';
            END IF;

            IF TG_OP = 'UPDATE' AND OLD.status <> 'OPEN'
               AND NEW.status IS DISTINCT FROM OLD.status THEN
                RAISE EXCEPTION 'A closed loan cannot be reopened or changed';
            END IF;

            IF NEW.status = 'OPEN' THEN
                IF NOT EXISTS (
                    SELECT 1
                    FROM clients c
                    JOIN profiles p ON p.id = c.id
                    WHERE c.id = NEW.client_id
                      AND p.is_active
                      AND NOT c.is_penalized
                ) THEN
                    RAISE EXCEPTION 'Client is inactive, penalized, or does not exist';
                END IF;

                SELECT * INTO copy_record
                FROM copies WHERE id = NEW.copy_id FOR UPDATE;
                IF NOT FOUND OR NOT copy_record.is_active
                   OR copy_record.status <> 'AVAILABLE' THEN
                    RAISE EXCEPTION 'Copy is not available for loan';
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM sale_items si
                    JOIN sales s ON s.id = si.sale_id
                    WHERE si.copy_id = NEW.copy_id
                      AND s.status IN ('PENDING', 'CONFIRMED')
                ) THEN
                    RAISE EXCEPTION 'Copy belongs to an active sale';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validate_loan
        BEFORE INSERT OR UPDATE ON loans
        FOR EACH ROW EXECUTE FUNCTION validate_loan()
        """
    )
    op.execute(
        """
        CREATE FUNCTION apply_loan_copy_state() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            PERFORM set_config('libstock.employee_id', NEW.employee_id::text, true);
            IF TG_OP = 'INSERT' THEN
                UPDATE copies SET status = 'BORROWED' WHERE id = NEW.copy_id;
            ELSIF OLD.status = 'OPEN' AND NEW.status IN ('RETURNED', 'CANCELLED') THEN
                UPDATE copies SET status = 'AVAILABLE' WHERE id = NEW.copy_id;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_apply_loan_copy_state
        AFTER INSERT OR UPDATE OF status, returned_at ON loans
        FOR EACH ROW EXECUTE FUNCTION apply_loan_copy_state()
        """
    )

    # Itens só entram em vendas pendentes, e somente quando o exemplar pode ser vendido.
    op.execute(
        """
        CREATE FUNCTION validate_sale_item() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            target_sale_id bigint;
            sale_state sale_status;
            copy_record copies%ROWTYPE;
        BEGIN
            target_sale_id := COALESCE(NEW.sale_id, OLD.sale_id);
            SELECT status INTO sale_state FROM sales WHERE id = target_sale_id;
            IF sale_state IS NULL OR sale_state <> 'PENDING' THEN
                RAISE EXCEPTION 'Items can only be changed in a pending sale';
            END IF;

            IF TG_OP <> 'DELETE' THEN
                SELECT * INTO copy_record
                FROM copies WHERE id = NEW.copy_id FOR UPDATE;
                IF NOT FOUND OR NOT copy_record.is_active
                   OR copy_record.destination <> 'COMMERCIAL'
                   OR copy_record.status <> 'AVAILABLE' THEN
                    RAISE EXCEPTION 'Only an active, available commercial copy can be sold';
                END IF;

                IF EXISTS (
                    SELECT 1 FROM loans
                    WHERE copy_id = NEW.copy_id AND status = 'OPEN'
                ) THEN
                    RAISE EXCEPTION 'A borrowed copy cannot be sold';
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM sale_items si
                    JOIN sales s ON s.id = si.sale_id
                    WHERE si.copy_id = NEW.copy_id
                      AND si.id <> COALESCE(NEW.id, -1)
                      AND s.status IN ('PENDING', 'CONFIRMED')
                ) THEN
                    RAISE EXCEPTION 'Copy already belongs to an active sale';
                END IF;
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validate_sale_item
        BEFORE INSERT OR UPDATE OR DELETE ON sale_items
        FOR EACH ROW EXECUTE FUNCTION validate_sale_item()
        """
    )
    op.execute(
        """
        CREATE FUNCTION refresh_sale_total() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            changed_sale_id bigint;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                changed_sale_id := OLD.sale_id;
            ELSE
                changed_sale_id := NEW.sale_id;
            END IF;
            UPDATE sales
            SET total_amount = COALESCE(
                (SELECT sum(unit_price) FROM sale_items WHERE sale_id = changed_sale_id),
                0
            )
            WHERE id = changed_sale_id;

            IF TG_OP = 'UPDATE' AND OLD.sale_id <> NEW.sale_id THEN
                UPDATE sales
                SET total_amount = COALESCE(
                    (SELECT sum(unit_price) FROM sale_items WHERE sale_id = OLD.sale_id),
                    0
                )
                WHERE id = OLD.sale_id;
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_refresh_sale_total
        AFTER INSERT OR UPDATE OR DELETE ON sale_items
        FOR EACH ROW EXECUTE FUNCTION refresh_sale_total()
        """
    )
    op.execute(
        """
        CREATE FUNCTION normalize_sale_total() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.total_amount := COALESCE(
                (SELECT sum(unit_price) FROM sale_items WHERE sale_id = NEW.id),
                0
            );
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_normalize_sale_total
        BEFORE INSERT OR UPDATE OF total_amount ON sales
        FOR EACH ROW EXECUTE FUNCTION normalize_sale_total()
        """
    )
    op.execute(
        """
        CREATE FUNCTION validate_sale_transition() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            invalid_count integer;
            item_count integer;
        BEGIN
            IF TG_OP = 'INSERT' AND NEW.status = 'CONFIRMED' THEN
                RAISE EXCEPTION 'Create the pending sale and its items before confirmation';
            END IF;

            IF TG_OP = 'UPDATE' AND OLD.status = 'CONFIRMED'
               AND NEW.status <> 'CONFIRMED' THEN
                RAISE EXCEPTION 'A confirmed sale is final and cannot be cancelled';
            END IF;

            IF TG_OP = 'UPDATE' AND NEW.status = 'CONFIRMED'
               AND OLD.status <> 'CONFIRMED' THEN
                SELECT count(*) INTO item_count FROM sale_items WHERE sale_id = NEW.id;
                IF item_count = 0 THEN
                    RAISE EXCEPTION 'A sale without items cannot be confirmed';
                END IF;

                PERFORM c.id
                FROM copies c
                JOIN sale_items si ON si.copy_id = c.id
                WHERE si.sale_id = NEW.id
                ORDER BY c.id
                FOR UPDATE OF c;

                SELECT count(*) INTO invalid_count
                FROM sale_items si
                JOIN copies c ON c.id = si.copy_id
                WHERE si.sale_id = NEW.id
                  AND (NOT c.is_active OR c.destination <> 'COMMERCIAL'
                       OR c.status <> 'AVAILABLE'
                       OR EXISTS (
                           SELECT 1 FROM loans l
                           WHERE l.copy_id = c.id AND l.status = 'OPEN'
                       ));
                IF invalid_count > 0 THEN
                    RAISE EXCEPTION 'Sale contains a copy that cannot be sold';
                END IF;

                NEW.total_amount := (
                    SELECT sum(unit_price) FROM sale_items WHERE sale_id = NEW.id
                );
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validate_sale_transition
        BEFORE INSERT OR UPDATE OF status ON sales
        FOR EACH ROW EXECUTE FUNCTION validate_sale_transition()
        """
    )
    op.execute(
        """
        CREATE FUNCTION apply_sale_copy_state() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.status <> 'CONFIRMED' AND NEW.status = 'CONFIRMED' THEN
                PERFORM set_config('libstock.employee_id', NEW.employee_id::text, true);
                UPDATE copies c
                SET status = 'SOLD'
                FROM sale_items si
                WHERE si.sale_id = NEW.id AND si.copy_id = c.id;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_apply_sale_copy_state
        AFTER UPDATE OF status ON sales
        FOR EACH ROW EXECUTE FUNCTION apply_sale_copy_state()
        """
    )

    # Reserva ativa recebe posição única e só existe para cliente apto e título
    # comercial sem disponibilidade imediata.
    op.execute(
        """
        CREATE FUNCTION validate_purchase_reservation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            fulfilled_book_id bigint;
            fulfilled_destination destination_type;
            activating boolean;
        BEGIN
            activating := TG_OP = 'INSERT';
            IF TG_OP = 'UPDATE' THEN
                activating := OLD.status NOT IN ('WAITING', 'NOTIFIED');
            END IF;

            IF NEW.status IN ('WAITING', 'NOTIFIED') THEN
                IF NOT EXISTS (
                    SELECT 1
                    FROM clients c
                    JOIN profiles p ON p.id = c.id
                    WHERE c.id = NEW.client_id
                      AND p.is_active
                      AND NOT c.is_penalized
                ) THEN
                    RAISE EXCEPTION 'Client is inactive, penalized, or does not exist';
                END IF;

                IF activating THEN
                    PERFORM 1 FROM books WHERE id = NEW.book_id FOR UPDATE;
                    IF NOT EXISTS (
                        SELECT 1 FROM copies
                        WHERE book_id = NEW.book_id
                          AND destination = 'COMMERCIAL'
                          AND is_active
                          AND status IN ('BORROWED', 'RESERVED')
                    ) THEN
                        RAISE EXCEPTION 'No commercial copy is expected to become available';
                    END IF;
                    IF EXISTS (
                        SELECT 1 FROM copies
                        WHERE book_id = NEW.book_id
                          AND destination = 'COMMERCIAL'
                          AND is_active AND status = 'AVAILABLE'
                    ) THEN
                        RAISE EXCEPTION 'An immediately available commercial copy cannot be reserved';
                    END IF;
                END IF;

                IF NEW.queue_position IS NULL THEN
                    SELECT COALESCE(max(queue_position), 0) + 1
                    INTO NEW.queue_position
                    FROM purchase_reservations
                    WHERE book_id = NEW.book_id
                      AND status IN ('WAITING', 'NOTIFIED');
                END IF;
            END IF;

            IF NEW.fulfilled_copy_id IS NOT NULL THEN
                SELECT book_id, destination
                INTO fulfilled_book_id, fulfilled_destination
                FROM copies WHERE id = NEW.fulfilled_copy_id;
                IF fulfilled_book_id IS DISTINCT FROM NEW.book_id
                   OR fulfilled_destination IS DISTINCT FROM 'COMMERCIAL' THEN
                    RAISE EXCEPTION 'Fulfilled copy must be commercial and belong to the reserved book';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validate_purchase_reservation
        BEFORE INSERT OR UPDATE ON purchase_reservations
        FOR EACH ROW EXECUTE FUNCTION validate_purchase_reservation()
        """
    )

    # O papel primário do funcionário deve fazer parte de seus papéis de usuário.
    op.execute(
        """
        INSERT INTO user_roles (user_id, role_id)
        SELECT id, role_id FROM employees
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        CREATE FUNCTION check_employee_primary_role() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            employee_id_value integer;
        BEGIN
            IF TG_TABLE_NAME = 'employees' THEN
                employee_id_value := NEW.id;
                IF NOT EXISTS (
                    SELECT 1
                    FROM employees e
                    JOIN user_roles ur
                      ON ur.user_id = e.id AND ur.role_id = e.role_id
                    WHERE e.id = employee_id_value
                ) THEN
                    RAISE EXCEPTION 'Employee primary role must exist in user_roles';
                END IF;
            ELSE
                FOR employee_id_value IN
                    SELECT DISTINCT value
                    FROM unnest(ARRAY[
                        OLD.user_id,
                        CASE WHEN TG_OP = 'UPDATE' THEN NEW.user_id END
                    ]) AS value
                    WHERE value IS NOT NULL
                LOOP
                    IF EXISTS (SELECT 1 FROM employees WHERE id = employee_id_value)
                       AND NOT EXISTS (
                           SELECT 1
                           FROM employees e
                           JOIN user_roles ur
                             ON ur.user_id = e.id AND ur.role_id = e.role_id
                           WHERE e.id = employee_id_value
                       ) THEN
                        RAISE EXCEPTION 'Employee primary role must exist in user_roles';
                    END IF;
                END LOOP;
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_employee_primary_role
        AFTER INSERT OR UPDATE OF role_id ON employees
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION check_employee_primary_role()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_user_role_keeps_employee_primary
        AFTER UPDATE OR DELETE ON user_roles
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION check_employee_primary_role()
        """
    )

    # O modelo conceitual exige ao menos um exemplar ativo para cada obra ativa.
    # A validação adiada permite cadastrar Book e Copy na mesma transação.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM books b
                WHERE b.is_active
                  AND NOT EXISTS (
                      SELECT 1 FROM copies c
                      WHERE c.book_id = b.id AND c.is_active
                  )
            ) THEN
                RAISE EXCEPTION
                    'Active books without active copies must be corrected before migration';
            END IF;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION check_active_book_has_copy() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.is_active
               AND NOT EXISTS (
                   SELECT 1 FROM copies
                   WHERE book_id = NEW.id AND is_active
               ) THEN
                RAISE EXCEPTION 'An active book requires at least one active copy';
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_active_book_has_copy
        AFTER INSERT OR UPDATE OF is_active ON books
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION check_active_book_has_copy()
        """
    )
    op.execute(
        """
        CREATE FUNCTION check_copy_keeps_active_book_valid() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            affected_book_id bigint;
        BEGIN
            affected_book_id := OLD.book_id;
            IF EXISTS (SELECT 1 FROM books WHERE id = affected_book_id AND is_active)
               AND NOT EXISTS (
                   SELECT 1 FROM copies
                   WHERE book_id = affected_book_id AND is_active
               ) THEN
                RAISE EXCEPTION 'An active book requires at least one active copy';
            END IF;

            IF TG_OP <> 'DELETE' AND NEW.book_id IS DISTINCT FROM affected_book_id THEN
                affected_book_id := NEW.book_id;
                IF EXISTS (SELECT 1 FROM books WHERE id = affected_book_id AND is_active)
                   AND NOT EXISTS (
                       SELECT 1 FROM copies
                       WHERE book_id = affected_book_id AND is_active
                   ) THEN
                    RAISE EXCEPTION 'An active book requires at least one active copy';
                END IF;
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_copy_keeps_active_book_valid
        AFTER UPDATE OF book_id, is_active OR DELETE ON copies
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION check_copy_keeps_active_book_valid()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_copy_keeps_active_book_valid ON copies")
    op.execute("DROP FUNCTION IF EXISTS check_copy_keeps_active_book_valid()")
    op.execute("DROP TRIGGER IF EXISTS trg_active_book_has_copy ON books")
    op.execute("DROP FUNCTION IF EXISTS check_active_book_has_copy()")
    op.execute("DROP TRIGGER IF EXISTS trg_user_role_keeps_employee_primary ON user_roles")
    op.execute("DROP TRIGGER IF EXISTS trg_employee_primary_role ON employees")
    op.execute("DROP FUNCTION IF EXISTS check_employee_primary_role()")
    op.execute("DROP TRIGGER IF EXISTS trg_validate_purchase_reservation ON purchase_reservations")
    op.execute("DROP FUNCTION IF EXISTS validate_purchase_reservation()")
    op.execute("DROP TRIGGER IF EXISTS trg_apply_sale_copy_state ON sales")
    op.execute("DROP FUNCTION IF EXISTS apply_sale_copy_state()")
    op.execute("DROP TRIGGER IF EXISTS trg_validate_sale_transition ON sales")
    op.execute("DROP FUNCTION IF EXISTS validate_sale_transition()")
    op.execute("DROP TRIGGER IF EXISTS trg_normalize_sale_total ON sales")
    op.execute("DROP FUNCTION IF EXISTS normalize_sale_total()")
    op.execute("DROP TRIGGER IF EXISTS trg_refresh_sale_total ON sale_items")
    op.execute("DROP FUNCTION IF EXISTS refresh_sale_total()")
    op.execute("DROP TRIGGER IF EXISTS trg_validate_sale_item ON sale_items")
    op.execute("DROP FUNCTION IF EXISTS validate_sale_item()")
    op.execute("DROP TRIGGER IF EXISTS trg_apply_loan_copy_state ON loans")
    op.execute("DROP FUNCTION IF EXISTS apply_loan_copy_state()")
    op.execute("DROP TRIGGER IF EXISTS trg_validate_loan ON loans")
    op.execute("DROP FUNCTION IF EXISTS validate_loan()")
    op.execute("DROP TRIGGER IF EXISTS trg_guard_copy_integrity ON copies")
    op.execute("DROP FUNCTION IF EXISTS guard_copy_integrity()")
    for table in ("books", "copies"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_audit_{table} ON {table}")
    op.execute("DROP FUNCTION IF EXISTS audit_inventory_change()")
    op.execute("DROP FUNCTION IF EXISTS current_audit_employee_id()")
    for table in ("profiles", "books", "copies"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    op.execute("DROP INDEX IF EXISTS uq_active_reservation_book_queue")
    op.execute("ALTER TABLE notifications DROP CONSTRAINT IF EXISTS chk_notification_state")
    op.execute("ALTER TABLE purchase_reservations DROP CONSTRAINT IF EXISTS chk_reservation_state")
    op.execute("ALTER TABLE loans DROP CONSTRAINT IF EXISTS chk_loan_status_dates")
    op.execute("ALTER TABLE copies DROP CONSTRAINT IF EXISTS chk_didactic_without_sale_price")
    op.execute("ALTER TABLE sale_items ADD CONSTRAINT uq_sale_item_copy UNIQUE (copy_id)")
