"""Cria o domínio integrado à autenticação própria.

Revision ID: 20260902_0002
Revises: 20260901_0001
"""
from collections.abc import Sequence

from alembic import op


revision: str = "20260902_0002"
down_revision: str | None = "20260901_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ENUMS = (
    "CREATE TYPE notification_channel AS ENUM ('EMAIL', 'IN_APP')",
    "CREATE TYPE destination_type AS ENUM ('DIDACTIC', 'COMMERCIAL')",
    "CREATE TYPE copy_status AS ENUM ('AVAILABLE', 'BORROWED', 'SOLD', 'RESERVED', 'INACTIVE')",
    "CREATE TYPE loan_status AS ENUM ('OPEN', 'RETURNED', 'CANCELLED')",
    "CREATE TYPE sale_status AS ENUM ('PENDING', 'CONFIRMED', 'CANCELLED')",
    "CREATE TYPE reservation_status AS ENUM ('WAITING', 'NOTIFIED', 'FULFILLED', 'CANCELLED', 'EXPIRED')",
    "CREATE TYPE notification_status AS ENUM ('PENDING', 'SENT', 'READ', 'FAILED')",
)


TABLES = (
    """
    CREATE TABLE profiles (
        id integer PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        phone varchar(30),
        notification_preference notification_channel NOT NULL DEFAULT 'IN_APP',
        is_active boolean NOT NULL DEFAULT true,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE roles (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        name varchar(50) NOT NULL UNIQUE,
        description varchar(255)
    )
    """,
    """
    CREATE TABLE clients (
        id integer PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
        registration_number varchar(50) UNIQUE,
        is_penalized boolean NOT NULL DEFAULT false,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE employees (
        id integer PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
        employee_code varchar(50) NOT NULL UNIQUE,
        role_id bigint NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE books (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        isbn varchar(17) UNIQUE,
        title varchar(255) NOT NULL,
        author varchar(255) NOT NULL,
        genre varchar(100),
        publication_year smallint,
        publisher varchar(150),
        edition varchar(50),
        cover_url text,
        is_active boolean NOT NULL DEFAULT true,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT chk_book_publication_year CHECK (
            publication_year IS NULL OR publication_year BETWEEN 1000 AND 2100
        )
    )
    """,
    """
    CREATE TABLE copies (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        book_id bigint NOT NULL REFERENCES books(id) ON DELETE RESTRICT,
        barcode varchar(100) NOT NULL UNIQUE,
        destination destination_type NOT NULL,
        status copy_status NOT NULL DEFAULT 'AVAILABLE',
        condition varchar(30),
        sale_price numeric(10,2),
        acquired_at date,
        is_active boolean NOT NULL DEFAULT true,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT chk_copy_sale_price CHECK (sale_price IS NULL OR sale_price >= 0),
        CONSTRAINT chk_commercial_price CHECK (
            destination <> 'COMMERCIAL' OR sale_price IS NOT NULL
        )
    )
    """,
    """
    CREATE TABLE loans (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        copy_id bigint NOT NULL REFERENCES copies(id) ON DELETE RESTRICT,
        client_id integer NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
        employee_id integer NOT NULL REFERENCES employees(id) ON DELETE RESTRICT,
        loan_date timestamptz NOT NULL DEFAULT now(),
        due_date timestamptz NOT NULL,
        returned_at timestamptz,
        status loan_status NOT NULL DEFAULT 'OPEN',
        created_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT chk_loan_due_date CHECK (due_date > loan_date),
        CONSTRAINT chk_loan_return_date CHECK (
            returned_at IS NULL OR returned_at >= loan_date
        )
    )
    """,
    """
    CREATE TABLE sales (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        client_id integer REFERENCES clients(id) ON DELETE RESTRICT,
        employee_id integer NOT NULL REFERENCES employees(id) ON DELETE RESTRICT,
        sale_date timestamptz NOT NULL DEFAULT now(),
        total_amount numeric(12,2) NOT NULL DEFAULT 0,
        status sale_status NOT NULL DEFAULT 'PENDING',
        created_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT chk_sale_total CHECK (total_amount >= 0)
    )
    """,
    """
    CREATE TABLE sale_items (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        sale_id bigint NOT NULL REFERENCES sales(id) ON DELETE RESTRICT,
        copy_id bigint NOT NULL REFERENCES copies(id) ON DELETE RESTRICT,
        unit_price numeric(10,2) NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT uq_sale_item_copy UNIQUE (copy_id),
        CONSTRAINT chk_sale_item_price CHECK (unit_price >= 0)
    )
    """,
    """
    CREATE TABLE purchase_reservations (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        book_id bigint NOT NULL REFERENCES books(id) ON DELETE RESTRICT,
        client_id integer NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
        fulfilled_copy_id bigint REFERENCES copies(id) ON DELETE RESTRICT,
        requested_at timestamptz NOT NULL DEFAULT now(),
        queue_position integer,
        status reservation_status NOT NULL DEFAULT 'WAITING',
        notified_at timestamptz,
        expires_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT chk_reservation_queue_position CHECK (
            queue_position IS NULL OR queue_position > 0
        ),
        CONSTRAINT chk_reservation_expiration CHECK (
            expires_at IS NULL OR expires_at > requested_at
        )
    )
    """,
    """
    CREATE TABLE notifications (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id integer NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
        type varchar(50) NOT NULL,
        channel notification_channel NOT NULL,
        subject varchar(255),
        message text NOT NULL,
        status notification_status NOT NULL DEFAULT 'PENDING',
        created_at timestamptz NOT NULL DEFAULT now(),
        sent_at timestamptz,
        read_at timestamptz
    )
    """,
    """
    CREATE TABLE audit_logs (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        employee_id integer REFERENCES employees(id) ON DELETE RESTRICT,
        entity_type varchar(100) NOT NULL,
        entity_id varchar(100) NOT NULL,
        operation varchar(100) NOT NULL,
        old_value jsonb,
        new_value jsonb,
        occurred_at timestamptz NOT NULL DEFAULT now()
    )
    """,
)


INDEXES = (
    "CREATE UNIQUE INDEX uq_loans_open_copy ON loans(copy_id) WHERE status = 'OPEN'",
    "CREATE INDEX idx_loans_client_status ON loans(client_id, status)",
    "CREATE INDEX idx_loans_due_date ON loans(due_date)",
    "CREATE INDEX idx_sales_employee ON sales(employee_id)",
    "CREATE INDEX idx_sales_client ON sales(client_id)",
    "CREATE INDEX idx_sale_items_sale ON sale_items(sale_id)",
    "CREATE UNIQUE INDEX uq_active_reservation_client_book ON purchase_reservations(client_id, book_id) WHERE status IN ('WAITING', 'NOTIFIED')",
    "CREATE INDEX idx_books_title ON books(title)",
    "CREATE INDEX idx_books_author ON books(author)",
    "CREATE INDEX idx_copies_book ON copies(book_id)",
    "CREATE INDEX idx_copies_book_status ON copies(book_id, status)",
    "CREATE INDEX idx_copies_destination_status ON copies(destination, status)",
    "CREATE INDEX idx_sales_date ON sales(sale_date)",
    "CREATE INDEX idx_reservations_book_status ON purchase_reservations(book_id, status)",
    "CREATE INDEX idx_reservations_client ON purchase_reservations(client_id)",
    "CREATE INDEX idx_notifications_user_status ON notifications(user_id, status)",
    "CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id)",
    "CREATE INDEX idx_audit_employee ON audit_logs(employee_id)",
    "CREATE INDEX idx_audit_occurred_at ON audit_logs(occurred_at)",
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("O domínio do LibStock requer PostgreSQL.")

    for statement in ENUMS:
        op.execute(statement)
    for statement in TABLES:
        op.execute(statement)
    for statement in INDEXES:
        op.execute(statement)

    op.execute(
        """
        CREATE VIEW book_availability AS
        SELECT b.id AS book_id, b.isbn, b.title, b.author,
            count(c.id) FILTER (WHERE c.destination = 'COMMERCIAL' AND c.status = 'AVAILABLE' AND c.is_active) AS available_for_sale,
            count(c.id) FILTER (WHERE c.destination = 'DIDACTIC' AND c.status = 'AVAILABLE' AND c.is_active) AS available_for_loan,
            count(c.id) FILTER (WHERE c.status = 'BORROWED' AND c.is_active) AS borrowed_count
        FROM books b LEFT JOIN copies c ON c.book_id = b.id
        WHERE b.is_active
        GROUP BY b.id, b.isbn, b.title, b.author
        """
    )
    op.execute(
        """
        CREATE VIEW overdue_loans AS
        SELECT id AS loan_id, client_id, copy_id, loan_date, due_date,
            now() - due_date AS overdue_duration
        FROM loans
        WHERE status = 'OPEN' AND returned_at IS NULL AND due_date < now()
        """
    )
    op.execute(
        """
        CREATE FUNCTION prevent_audit_log_modification() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Audit logs cannot be modified or deleted';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_prevent_audit_log_modification
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification()
        """
    )
    op.execute(
        """
        INSERT INTO roles (name, description) VALUES
            ('ATTENDANT', 'Atendente responsável pelas operações de balcão'),
            ('STOCK_KEEPER', 'Responsável pela organização e manutenção do acervo'),
            ('MANAGER', 'Gerente autorizado a executar operações críticas'),
            ('ADMINISTRATOR', 'Administrador do sistema')
        ON CONFLICT (name) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_audit_log_modification ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification()")
    op.execute("DROP VIEW IF EXISTS overdue_loans")
    op.execute("DROP VIEW IF EXISTS book_availability")
    for table in (
            "audit_logs",
            "notifications",
            "purchase_reservations",
            "sale_items",
            "sales",
            "loans",
            "copies",
            "books",
            "employees",
            "clients",
            "roles",
            "profiles",
    ):
        op.execute(f"DROP TABLE {table}")
    for enum_name in reversed(
        (
            "notification_status",
            "reservation_status",
            "sale_status",
            "loan_status",
            "copy_status",
            "destination_type",
            "notification_channel",
        )
    ):
        op.execute(f"DROP TYPE {enum_name}")
