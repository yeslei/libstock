"""Link availability notifications to reservations and prevent duplicate events.

Existing notifications remain unchanged. No historical messages are generated.
"""
import sqlalchemy as sa
from alembic import op

revision = "20261109_0018"
down_revision = "20261004_0017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("notifications", sa.Column("reservation_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_notifications_reservation_id", "notifications", "purchase_reservations",
                          ["reservation_id"], ["id"], ondelete="RESTRICT")
    op.create_index("uq_notification_reservation_event", "notifications", ["type", "reservation_id"],
                    unique=True, postgresql_where=sa.text("reservation_id IS NOT NULL"))
    op.create_index("idx_notifications_pending_email", "notifications", ["id"],
                    postgresql_where=sa.text("status = 'PENDING' AND channel = 'EMAIL'"))


def downgrade():
    op.drop_index("idx_notifications_pending_email", table_name="notifications")
    op.drop_index("uq_notification_reservation_event", table_name="notifications")
    op.drop_constraint("fk_notifications_reservation_id", "notifications", type_="foreignkey")
    op.drop_column("notifications", "reservation_id")
