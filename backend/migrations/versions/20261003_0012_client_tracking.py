"""Connect existing requests to circulation and allocated purchase copies."""
from alembic import op
import sqlalchemy as sa

revision = '20261003_0012'
down_revision = '20261003_0011'
branch_labels = None
depends_on = None

OLD_VALIDATION = """
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
NEW_VALIDATION = """
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
    op.add_column('loan_requests', sa.Column('loan_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key('fk_loan_request_loan', 'loan_requests', 'loans', ['loan_id'], ['id'], ondelete='RESTRICT')
    op.create_unique_constraint('uq_loan_request_loan', 'loan_requests', ['loan_id'])
    op.drop_index('uq_pending_loan_request_client_book', table_name='loan_requests')
    op.create_index('uq_pending_loan_request_client_book', 'loan_requests', ['client_id', 'book_id'], unique=True, postgresql_where=sa.text('loan_id IS NULL'))
    op.add_column('purchase_reservations', sa.Column('allocated_copy_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key('fk_reservation_allocated_copy', 'purchase_reservations', 'copies', ['allocated_copy_id'], ['id'], ondelete='RESTRICT')
    op.create_index('uq_notified_reservation_copy', 'purchase_reservations', ['allocated_copy_id'], unique=True, postgresql_where=sa.text("status = 'NOTIFIED'"))
    op.add_column('purchase_requests', sa.Column('reservation_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key('fk_purchase_request_reservation', 'purchase_requests', 'purchase_reservations', ['reservation_id'], ['id'], ondelete='RESTRICT')
    op.create_unique_constraint('uq_purchase_request_reservation', 'purchase_requests', ['reservation_id'])
    op.drop_index('uq_pending_purchase_request_client_book', table_name='purchase_requests')
    op.create_index('idx_purchase_request_client_book', 'purchase_requests', ['client_id','book_id'])
    op.execute(NEW_VALIDATION)
    op.execute("""
        DO $$ DECLARE r record; reservation_value bigint; copy_value bigint; position_value integer; state_value reservation_status;
        BEGIN
          FOR r IN SELECT * FROM purchase_requests ORDER BY created_at, id LOOP
            SELECT id INTO reservation_value FROM purchase_reservations
              WHERE client_id = r.client_id AND book_id = r.book_id AND status IN ('WAITING','NOTIFIED');
            IF reservation_value IS NULL THEN
              SELECT c.id INTO copy_value FROM copies c WHERE c.book_id = r.book_id AND c.is_active
                AND c.destination = 'COMMERCIAL' AND c.status = 'AVAILABLE'
                AND NOT EXISTS (SELECT 1 FROM purchase_reservations pr WHERE pr.allocated_copy_id=c.id AND pr.status='NOTIFIED')
                AND NOT EXISTS (SELECT 1 FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE si.copy_id=c.id AND s.status IN ('PENDING','CONFIRMED'))
                ORDER BY c.id LIMIT 1;
              state_value := CASE WHEN copy_value IS NOT NULL THEN 'NOTIFIED'::reservation_status ELSE 'WAITING'::reservation_status END;
              IF NOT EXISTS (SELECT 1 FROM clients c JOIN profiles p ON p.id=c.id JOIN users u ON u.id=c.id WHERE c.id=r.client_id AND p.is_active AND u.is_active AND NOT c.is_penalized)
                 OR (copy_value IS NULL AND NOT EXISTS (SELECT 1 FROM copies WHERE book_id=r.book_id AND is_active AND destination='COMMERCIAL' AND status IN ('BORROWED','RESERVED'))) THEN
                state_value := 'CANCELLED';
              END IF;
              SELECT coalesce(max(queue_position),0)+1 INTO position_value FROM purchase_reservations WHERE book_id=r.book_id AND status IN ('WAITING','NOTIFIED');
              INSERT INTO purchase_reservations (book_id,client_id,status,queue_position,allocated_copy_id,notified_at,requested_at)
                VALUES (r.book_id,r.client_id,state_value,position_value,copy_value,CASE WHEN state_value='NOTIFIED' THEN now() ELSE NULL END,r.created_at)
                RETURNING id INTO reservation_value;
            END IF;
            UPDATE purchase_requests SET reservation_id=reservation_value WHERE id=r.id;
          END LOOP;
        END $$
    """)
    op.execute("""
        CREATE FUNCTION link_client_loan_request() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          UPDATE loan_requests SET loan_id=NEW.id, updated_at=now()
            WHERE client_id=NEW.client_id AND loan_id IS NULL AND book_id=(SELECT book_id FROM copies WHERE id=NEW.copy_id);
          RETURN NEW;
        END $$
    """)
    op.execute('CREATE TRIGGER trg_link_client_loan_request AFTER INSERT ON loans FOR EACH ROW EXECUTE FUNCTION link_client_loan_request()')
    op.execute("""
        CREATE FUNCTION complete_client_purchase_reservation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.status='CONFIRMED' THEN
            UPDATE purchase_reservations r SET status='FULFILLED', fulfilled_copy_id=r.allocated_copy_id
              WHERE r.client_id=NEW.client_id AND r.status='NOTIFIED'
                AND EXISTS (SELECT 1 FROM sale_items si WHERE si.sale_id=NEW.id AND si.copy_id=r.allocated_copy_id);
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute('CREATE TRIGGER trg_complete_client_purchase_reservation AFTER UPDATE OF status ON sales FOR EACH ROW EXECUTE FUNCTION complete_client_purchase_reservation()')


def downgrade():
    op.execute('DROP TRIGGER trg_complete_client_purchase_reservation ON sales')
    op.execute('DROP FUNCTION complete_client_purchase_reservation()')
    op.execute('DROP TRIGGER trg_link_client_loan_request ON loans')
    op.execute('DROP FUNCTION link_client_loan_request()')
    op.execute(OLD_VALIDATION.replace('CREATE FUNCTION', 'CREATE OR REPLACE FUNCTION', 1))
    op.drop_index('idx_purchase_request_client_book', table_name='purchase_requests')
    op.create_index('uq_pending_purchase_request_client_book', 'purchase_requests', ['client_id','book_id'], unique=True)
    op.drop_constraint('uq_purchase_request_reservation', 'purchase_requests', type_='unique')
    op.drop_constraint('fk_purchase_request_reservation', 'purchase_requests', type_='foreignkey')
    op.drop_column('purchase_requests', 'reservation_id')
    op.drop_index('uq_notified_reservation_copy', table_name='purchase_reservations')
    op.drop_constraint('fk_reservation_allocated_copy', 'purchase_reservations', type_='foreignkey')
    op.drop_column('purchase_reservations', 'allocated_copy_id')
    op.drop_index('uq_pending_loan_request_client_book', table_name='loan_requests')
    op.create_index('uq_pending_loan_request_client_book', 'loan_requests', ['client_id','book_id'], unique=True)
    op.drop_constraint('uq_loan_request_loan', 'loan_requests', type_='unique')
    op.drop_constraint('fk_loan_request_loan', 'loan_requests', type_='foreignkey')
    op.drop_column('loan_requests', 'loan_id')
