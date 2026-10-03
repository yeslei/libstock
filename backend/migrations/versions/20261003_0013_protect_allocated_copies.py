"""Protect allocated commercial copies and audit circulation transitions."""
from alembic import op

revision = '20261003_0013'
down_revision = '20261003_0012'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE FUNCTION guard_allocated_sale_item() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          PERFORM 1 FROM copies WHERE id=NEW.copy_id FOR UPDATE;
          IF EXISTS (
            SELECT 1 FROM purchase_reservations r JOIN sales s ON s.id=NEW.sale_id
            WHERE r.allocated_copy_id=NEW.copy_id AND r.status='NOTIFIED'
              AND r.client_id IS DISTINCT FROM s.client_id
          ) THEN RAISE EXCEPTION 'Copy is allocated to another client'; END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_guard_allocated_sale_item BEFORE INSERT OR UPDATE ON sale_items
        FOR EACH ROW EXECUTE FUNCTION guard_allocated_sale_item();

        CREATE FUNCTION guard_allocated_copy_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS (SELECT 1 FROM purchase_reservations WHERE allocated_copy_id=OLD.id AND status='NOTIFIED') THEN
            IF NEW.book_id IS DISTINCT FROM OLD.book_id OR NEW.destination IS DISTINCT FROM OLD.destination
              OR NEW.is_active IS DISTINCT FROM OLD.is_active OR NEW.status NOT IN ('AVAILABLE','SOLD') THEN
              RAISE EXCEPTION 'An allocated copy cannot change book, destination, activity or availability';
            END IF;
            IF NEW.status='SOLD' AND NOT EXISTS (
              SELECT 1 FROM purchase_reservations r JOIN sale_items si ON si.copy_id=r.allocated_copy_id
                JOIN sales s ON s.id=si.sale_id
              WHERE r.allocated_copy_id=OLD.id AND r.status='NOTIFIED'
                AND s.status='CONFIRMED' AND s.client_id=r.client_id
            ) THEN RAISE EXCEPTION 'Allocated copy can only be sold to its client'; END IF;
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_guard_allocated_copy_change BEFORE UPDATE ON copies
        FOR EACH ROW EXECUTE FUNCTION guard_allocated_copy_change();

        CREATE FUNCTION audit_circulation_transition() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          INSERT INTO audit_logs (employee_id,entity_type,entity_id,operation,old_value,new_value)
          VALUES (current_audit_employee_id(),TG_TABLE_NAME,NEW.id::text,TG_OP,
            CASE WHEN TG_OP='UPDATE' THEN to_jsonb(OLD) ELSE NULL END,to_jsonb(NEW));
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_audit_purchase_reservation AFTER INSERT OR UPDATE ON purchase_reservations
        FOR EACH ROW EXECUTE FUNCTION audit_circulation_transition();
        CREATE TRIGGER trg_audit_loan_transition AFTER INSERT OR UPDATE ON loans
        FOR EACH ROW EXECUTE FUNCTION audit_circulation_transition();
        CREATE OR REPLACE FUNCTION apply_loan_copy_state() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          PERFORM set_config('libstock.employee_id', COALESCE(current_audit_employee_id(),NEW.employee_id)::text,true);
          IF TG_OP='INSERT' THEN
            UPDATE copies SET status='BORROWED' WHERE id=NEW.copy_id;
          ELSIF OLD.status='OPEN' AND NEW.status IN ('RETURNED','CANCELLED') THEN
            UPDATE copies SET status='AVAILABLE' WHERE id=NEW.copy_id;
          END IF;
          RETURN NEW;
        END $$;
    """)


def downgrade():
    op.execute("""
        DROP TRIGGER trg_audit_loan_transition ON loans;
        DROP TRIGGER trg_audit_purchase_reservation ON purchase_reservations;
        DROP FUNCTION audit_circulation_transition();
        DROP TRIGGER trg_guard_allocated_copy_change ON copies;
        DROP FUNCTION guard_allocated_copy_change();
        DROP TRIGGER trg_guard_allocated_sale_item ON sale_items;
        DROP FUNCTION guard_allocated_sale_item();
        CREATE OR REPLACE FUNCTION apply_loan_copy_state() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          PERFORM set_config('libstock.employee_id',NEW.employee_id::text,true);
          IF TG_OP='INSERT' THEN
            UPDATE copies SET status='BORROWED' WHERE id=NEW.copy_id;
          ELSIF OLD.status='OPEN' AND NEW.status IN ('RETURNED','CANCELLED') THEN
            UPDATE copies SET status='AVAILABLE' WHERE id=NEW.copy_id;
          END IF;
          RETURN NEW;
        END $$;
    """)
