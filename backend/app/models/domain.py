from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class NotificationChannel(str, Enum):
    EMAIL = "EMAIL"
    IN_APP = "IN_APP"


class DestinationType(str, Enum):
    DIDACTIC = "DIDACTIC"
    COMMERCIAL = "COMMERCIAL"


class CopyStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    BORROWED = "BORROWED"
    SOLD = "SOLD"
    RESERVED = "RESERVED"
    INACTIVE = "INACTIVE"


class LoanStatus(str, Enum):
    OPEN = "OPEN"
    RETURNED = "RETURNED"
    CANCELLED = "CANCELLED"


class SaleStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class ReservationStatus(str, Enum):
    WAITING = "WAITING"
    NOTIFIED = "NOTIFIED"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class NotificationStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    READ = "READ"
    FAILED = "FAILED"


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    phone: Mapped[str | None] = mapped_column(String(30))
    notification_preference: Mapped[NotificationChannel] = mapped_column(
        SqlEnum(NotificationChannel, name="notification_channel"),
        nullable=False,
        server_default=NotificationChannel.IN_APP.value,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(255))

    users: Mapped[list["UserRole"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship(back_populates="users")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    registration_number: Mapped[str | None] = mapped_column(String(50), unique=True)
    is_penalized: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    employee_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint(
            "publication_year IS NULL OR publication_year BETWEEN 1000 AND 2100",
            name="chk_book_publication_year",
        ),
        Index("idx_books_title", "title"),
        Index("idx_books_author", "author"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    isbn: Mapped[str | None] = mapped_column(String(17), unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    genre: Mapped[str | None] = mapped_column(String(100))
    publication_year: Mapped[int | None] = mapped_column(SmallInteger)
    publisher: Mapped[str | None] = mapped_column(String(150))
    edition: Mapped[str | None] = mapped_column(String(50))
    cover_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Copy(Base):
    __tablename__ = "copies"
    __table_args__ = (
        CheckConstraint("sale_price IS NULL OR sale_price >= 0", name="chk_copy_sale_price"),
        CheckConstraint(
            "destination <> 'COMMERCIAL' OR sale_price IS NOT NULL",
            name="chk_commercial_price",
        ),
        CheckConstraint(
            "destination = 'COMMERCIAL' OR sale_price IS NULL",
            name="chk_didactic_without_sale_price",
        ),
        Index("idx_copies_book", "book_id"),
        Index("idx_copies_book_status", "book_id", "status"),
        Index("idx_copies_destination_status", "destination", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("books.id", ondelete="RESTRICT"), nullable=False)
    barcode: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    destination: Mapped[DestinationType] = mapped_column(SqlEnum(DestinationType, name="destination_type"), nullable=False)
    status: Mapped[CopyStatus] = mapped_column(SqlEnum(CopyStatus, name="copy_status"), nullable=False, server_default=CopyStatus.AVAILABLE.value)
    condition: Mapped[str | None] = mapped_column(String(30))
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    acquired_at: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = (
        CheckConstraint("due_date > loan_date", name="chk_loan_due_date"),
        CheckConstraint("returned_at IS NULL OR returned_at >= loan_date", name="chk_loan_return_date"),
        CheckConstraint(
            "(status = 'OPEN' AND returned_at IS NULL) OR "
            "(status = 'RETURNED' AND returned_at IS NOT NULL) OR "
            "(status = 'CANCELLED' AND returned_at IS NULL)",
            name="chk_loan_status_dates",
        ),
        Index("uq_loans_open_copy", "copy_id", unique=True, postgresql_where=text("status = 'OPEN'")),
        Index("idx_loans_client_status", "client_id", "status"),
        Index("idx_loans_due_date", "due_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    copy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("copies.id", ondelete="RESTRICT"), nullable=False)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False)
    loan_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[LoanStatus] = mapped_column(SqlEnum(LoanStatus, name="loan_status"), nullable=False, server_default=LoanStatus.OPEN.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="chk_sale_total"),
        Index("idx_sales_employee", "employee_id"),
        Index("idx_sales_client", "client_id"),
        Index("idx_sales_date", "sale_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"))
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False)
    sale_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    status: Mapped[SaleStatus] = mapped_column(SqlEnum(SaleStatus, name="sale_status"), nullable=False, server_default=SaleStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SaleItem(Base):
    __tablename__ = "sale_items"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="chk_sale_item_price"),
        Index("idx_sale_items_sale", "sale_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False)
    copy_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("copies.id", ondelete="RESTRICT"), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PurchaseReservation(Base):
    __tablename__ = "purchase_reservations"
    __table_args__ = (
        CheckConstraint("queue_position IS NULL OR queue_position > 0", name="chk_reservation_queue_position"),
        CheckConstraint("expires_at IS NULL OR expires_at > requested_at", name="chk_reservation_expiration"),
        CheckConstraint(
            "(status = 'WAITING' AND queue_position IS NOT NULL "
            "AND notified_at IS NULL AND fulfilled_copy_id IS NULL) OR "
            "(status = 'NOTIFIED' AND queue_position IS NOT NULL "
            "AND notified_at IS NOT NULL AND fulfilled_copy_id IS NULL) OR "
            "(status = 'FULFILLED' AND fulfilled_copy_id IS NOT NULL) OR "
            "status IN ('CANCELLED', 'EXPIRED')",
            name="chk_reservation_state",
        ),
        Index("uq_active_reservation_client_book", "client_id", "book_id", unique=True, postgresql_where=text("status IN ('WAITING', 'NOTIFIED')")),
        Index("uq_active_reservation_book_queue", "book_id", "queue_position", unique=True, postgresql_where=text("status IN ('WAITING', 'NOTIFIED')")),
        Index("idx_reservations_book_status", "book_id", "status"),
        Index("idx_reservations_client", "client_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("books.id", ondelete="RESTRICT"), nullable=False)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    fulfilled_copy_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("copies.id", ondelete="RESTRICT"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    queue_position: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[ReservationStatus] = mapped_column(SqlEnum(ReservationStatus, name="reservation_status"), nullable=False, server_default=ReservationStatus.WAITING.value)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "(status = 'PENDING' AND sent_at IS NULL AND read_at IS NULL) OR "
            "(status = 'SENT' AND sent_at IS NOT NULL AND read_at IS NULL) OR "
            "(status = 'READ' AND sent_at IS NOT NULL AND read_at IS NOT NULL "
            "AND read_at >= sent_at) OR "
            "(status = 'FAILED' AND read_at IS NULL)",
            name="chk_notification_state",
        ),
        Index("idx_notifications_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[NotificationChannel] = mapped_column(SqlEnum(NotificationChannel, name="notification_channel"), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(SqlEnum(NotificationStatus, name="notification_status"), nullable=False, server_default=NotificationStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_employee", "employee_id"),
        Index("idx_audit_occurred_at", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("employees.id", ondelete="RESTRICT"))
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[dict | None] = mapped_column(JSONB)
    new_value: Mapped[dict | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
