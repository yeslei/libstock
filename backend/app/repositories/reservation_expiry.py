"""Lazy expiry of purchase reservations, shared by every flow that locks a book."""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.domain import PurchaseReservation, ReservationStatus


def expire_due_reservations(db: Session, book_id: int, now: datetime) -> int:
    """NOTIFIED reservations of a (locked) book past expires_at become EXPIRED.

    The allocated copy is released by the status change itself (a copy is held only while its
    reservation is NOTIFIED); allocated_copy_id is kept as history. Lock order: book, then reservations."""
    due = db.scalars(select(PurchaseReservation).where(
        PurchaseReservation.book_id == book_id, PurchaseReservation.status == ReservationStatus.NOTIFIED,
        PurchaseReservation.expires_at.is_not(None), PurchaseReservation.expires_at < now,
    ).order_by(PurchaseReservation.id).with_for_update().execution_options(populate_existing=True)).all()
    for reservation in due:
        reservation.status = ReservationStatus.EXPIRED
    if due:
        db.flush()
    return len(due)
