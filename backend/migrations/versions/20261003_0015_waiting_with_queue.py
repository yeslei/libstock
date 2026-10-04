"""Permite reserva WAITING com exemplar livre quando a obra já tem fila WAITING (Issue #150).

A precedência da fila é preservada: nova solicitação entra no fim da fila mesmo havendo exemplar livre.
Sem fila WAITING, a regra anterior continua valendo. A 0012 não é alterada."""
from alembic import op

revision = '20261003_0015'
down_revision = '20261003_0014'
branch_labels = None
depends_on = None

QUEUE_AWARE_VALIDATION = """
        CREATE OR REPLACE FUNCTION validate_purchase_reservation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            fulfilled_book_id bigint;
            fulfilled_destination destination_type;
            activating boolean;
            queued boolean;
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

                IF activating AND NEW.status = 'WAITING' THEN
                    PERFORM 1 FROM books WHERE id = NEW.book_id FOR UPDATE;
                    queued := EXISTS (
                        SELECT 1 FROM purchase_reservations pr
                        WHERE pr.book_id = NEW.book_id AND pr.status = 'WAITING' AND pr.id IS DISTINCT FROM NEW.id
                    );
                    IF queued THEN
                        IF NOT EXISTS (
                            SELECT 1 FROM copies
                            WHERE book_id = NEW.book_id
                              AND destination = 'COMMERCIAL'
                              AND is_active
                              AND status IN ('AVAILABLE', 'BORROWED', 'RESERVED')
                        ) THEN
                            RAISE EXCEPTION 'No commercial copy is expected to become available';
                        END IF;
                    ELSE
                        IF NOT EXISTS (
                            SELECT 1 FROM copies
                            WHERE book_id = NEW.book_id
                              AND destination = 'COMMERCIAL'
                              AND is_active
                              AND (status IN ('BORROWED', 'RESERVED') OR EXISTS (SELECT 1 FROM purchase_reservations pr WHERE pr.allocated_copy_id = copies.id AND pr.status = 'NOTIFIED'))
                        ) THEN
                            RAISE EXCEPTION 'No commercial copy is expected to become available';
                        END IF;
                        IF EXISTS (
                            SELECT 1 FROM copies
                            WHERE book_id = NEW.book_id
                              AND destination = 'COMMERCIAL'
                              AND is_active AND status = 'AVAILABLE' AND NOT EXISTS (SELECT 1 FROM purchase_reservations pr WHERE pr.allocated_copy_id = copies.id AND pr.status = 'NOTIFIED') AND NOT EXISTS (SELECT 1 FROM sale_items si JOIN sales ss ON ss.id = si.sale_id WHERE si.copy_id = copies.id AND ss.status IN ('PENDING', 'CONFIRMED'))
                        ) THEN
                            RAISE EXCEPTION 'An immediately available commercial copy cannot be reserved';
                        END IF;
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

            IF NEW.allocated_copy_id IS NOT NULL THEN
                IF NOT EXISTS (SELECT 1 FROM copies WHERE id = NEW.allocated_copy_id
                    AND book_id = NEW.book_id AND destination = 'COMMERCIAL') THEN
                    RAISE EXCEPTION 'Allocated copy must be commercial and belong to the reserved book';
                END IF;
            END IF;
            IF NEW.status = 'NOTIFIED' AND (TG_OP = 'INSERT' OR OLD.status = 'WAITING') THEN
                IF NEW.allocated_copy_id IS NULL OR NOT EXISTS (
                    SELECT 1 FROM copies WHERE id = NEW.allocated_copy_id AND is_active AND status = 'AVAILABLE' AND NOT EXISTS (SELECT 1 FROM purchase_reservations pr WHERE pr.allocated_copy_id = copies.id AND pr.status = 'NOTIFIED') AND NOT EXISTS (SELECT 1 FROM sale_items si JOIN sales ss ON ss.id = si.sale_id WHERE si.copy_id = copies.id AND ss.status IN ('PENDING', 'CONFIRMED'))
                ) THEN RAISE EXCEPTION 'An available commercial copy must be allocated'; END IF;
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

PREVIOUS_VALIDATION = """
        CREATE OR REPLACE FUNCTION validate_purchase_reservation() RETURNS trigger
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

                IF activating AND NEW.status = 'WAITING' THEN
                    PERFORM 1 FROM books WHERE id = NEW.book_id FOR UPDATE;
                    IF NOT EXISTS (
                        SELECT 1 FROM copies
                        WHERE book_id = NEW.book_id
                          AND destination = 'COMMERCIAL'
                          AND is_active
                          AND (status IN ('BORROWED', 'RESERVED') OR EXISTS (SELECT 1 FROM purchase_reservations pr WHERE pr.allocated_copy_id = copies.id AND pr.status = 'NOTIFIED'))
                    ) THEN
                        RAISE EXCEPTION 'No commercial copy is expected to become available';
                    END IF;
                    IF EXISTS (
                        SELECT 1 FROM copies
                        WHERE book_id = NEW.book_id
                          AND destination = 'COMMERCIAL'
                          AND is_active AND status = 'AVAILABLE' AND NOT EXISTS (SELECT 1 FROM purchase_reservations pr WHERE pr.allocated_copy_id = copies.id AND pr.status = 'NOTIFIED') AND NOT EXISTS (SELECT 1 FROM sale_items si JOIN sales ss ON ss.id = si.sale_id WHERE si.copy_id = copies.id AND ss.status IN ('PENDING', 'CONFIRMED'))
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

            IF NEW.allocated_copy_id IS NOT NULL THEN
                IF NOT EXISTS (SELECT 1 FROM copies WHERE id = NEW.allocated_copy_id
                    AND book_id = NEW.book_id AND destination = 'COMMERCIAL') THEN
                    RAISE EXCEPTION 'Allocated copy must be commercial and belong to the reserved book';
                END IF;
            END IF;
            IF NEW.status = 'NOTIFIED' AND (TG_OP = 'INSERT' OR OLD.status = 'WAITING') THEN
                IF NEW.allocated_copy_id IS NULL OR NOT EXISTS (
                    SELECT 1 FROM copies WHERE id = NEW.allocated_copy_id AND is_active AND status = 'AVAILABLE' AND NOT EXISTS (SELECT 1 FROM purchase_reservations pr WHERE pr.allocated_copy_id = copies.id AND pr.status = 'NOTIFIED') AND NOT EXISTS (SELECT 1 FROM sale_items si JOIN sales ss ON ss.id = si.sale_id WHERE si.copy_id = copies.id AND ss.status IN ('PENDING', 'CONFIRMED'))
                ) THEN RAISE EXCEPTION 'An available commercial copy must be allocated'; END IF;
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


def upgrade():
    op.execute(QUEUE_AWARE_VALIDATION)


def downgrade():
    op.execute(PREVIOUS_VALIDATION)
