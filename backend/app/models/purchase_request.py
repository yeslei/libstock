from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"
    __table_args__ = (
        CheckConstraint("status = 'PENDING'", name="chk_purchase_request_status"),
        Index("idx_purchase_request_client_book", "client_id", "book_id"),
        Index("idx_purchase_requests_book", "book_id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("books.id", ondelete="RESTRICT"), nullable=False)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    reservation_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("purchase_reservations.id", ondelete="RESTRICT"), unique=True)
    pickup_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'PENDING'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
