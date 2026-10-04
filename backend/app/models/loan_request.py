from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LoanRequest(Base):
    __tablename__ = "loan_requests"
    __table_args__ = (
        CheckConstraint("status = 'PENDING'", name="chk_loan_request_status"),
        CheckConstraint("due_date > pickup_date", name="chk_loan_request_dates"),
        CheckConstraint("due_date = (pickup_date + interval '1 month')::date", name="chk_loan_request_month"),
        Index("uq_pending_loan_request_client_book", "client_id", "book_id", unique=True, postgresql_where=text("loan_id IS NULL")),
        Index("idx_loan_requests_book", "book_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("books.id", ondelete="RESTRICT"), nullable=False)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    loan_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("loans.id", ondelete="RESTRICT"), unique=True)
    pickup_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'PENDING'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
