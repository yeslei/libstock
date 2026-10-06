"""Solicitações do cliente, distintas do empréstimo efetivo.

Revision ID: 20261003_0011
Revises: 20260908_0010
"""
from alembic import op
import sqlalchemy as sa

revision = "20261003_0011"
down_revision = "20260908_0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "loan_requests",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger(), sa.ForeignKey("books.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("pickup_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status = 'PENDING'", name="chk_loan_request_status"),
        sa.CheckConstraint("due_date > pickup_date", name="chk_loan_request_dates"),
        sa.CheckConstraint("due_date = (pickup_date + interval '1 month')::date", name="chk_loan_request_month"),
    )
    op.create_index("uq_pending_loan_request_client_book", "loan_requests", ["client_id", "book_id"], unique=True)
    op.create_index("idx_loan_requests_book", "loan_requests", ["book_id"])
    op.create_table(
        "purchase_requests",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger(), sa.ForeignKey("books.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("pickup_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status = 'PENDING'", name="chk_purchase_request_status"),
    )
    op.create_index("uq_pending_purchase_request_client_book", "purchase_requests", ["client_id", "book_id"], unique=True)
    op.create_index("idx_purchase_requests_book", "purchase_requests", ["book_id"])
    op.execute("""
        CREATE FUNCTION audit_client_request() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            INSERT INTO audit_logs (entity_type, entity_id, operation, new_value)
            VALUES (TG_TABLE_NAME, NEW.id::text, 'INSERT', to_jsonb(NEW));
            RETURN NEW;
        END;
        $$
    """)
    for table in ('loan_requests', 'purchase_requests'):
        op.execute(f"CREATE TRIGGER trg_audit_{table} AFTER INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION audit_client_request()")


def downgrade():
    for table in ('loan_requests', 'purchase_requests'):
        op.execute(f"DROP TRIGGER trg_audit_{table} ON {table}")
    op.execute("DROP FUNCTION audit_client_request()")
    op.drop_index("idx_purchase_requests_book", table_name="purchase_requests")
    op.drop_index("uq_pending_purchase_request_client_book", table_name="purchase_requests")
    op.drop_table("purchase_requests")
    op.drop_index("idx_loan_requests_book", table_name="loan_requests")
    op.drop_index("uq_pending_loan_request_client_book", table_name="loan_requests")
    op.drop_table("loan_requests")
