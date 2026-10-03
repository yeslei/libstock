"""One definition of a free copy for catalog, requests and circulation."""
from sqlalchemy import select
from app.models.domain import Copy, CopyStatus, DestinationType, PurchaseReservation, ReservationStatus, Sale, SaleItem, SaleStatus


def free_copies_statement(book_id: int | None = None):
    active_sale = select(SaleItem.id).join(Sale, Sale.id == SaleItem.sale_id).where(
        SaleItem.copy_id == Copy.id, Sale.status.in_([SaleStatus.PENDING, SaleStatus.CONFIRMED])
    ).exists()
    allocated = select(PurchaseReservation.id).where(
        PurchaseReservation.allocated_copy_id == Copy.id,
        PurchaseReservation.status == ReservationStatus.NOTIFIED,
    ).exists()
    statement = select(Copy).where(
        Copy.is_active.is_(True), Copy.status == CopyStatus.AVAILABLE, ~active_sale, ~allocated,
    )
    if book_id is not None:
        statement = statement.where(Copy.book_id == book_id)
    return statement.execution_options(populate_existing=True)


def reservable_commercial_statement(book_id: int | None = None):
    allocated = select(PurchaseReservation.id).where(
        PurchaseReservation.allocated_copy_id == Copy.id,
        PurchaseReservation.status == ReservationStatus.NOTIFIED,
    ).exists()
    statement = select(Copy).where(
        Copy.is_active.is_(True),
        Copy.destination == DestinationType.COMMERCIAL,
        Copy.status.in_([CopyStatus.BORROWED, CopyStatus.RESERVED]) | allocated,
    )
    return statement.where(Copy.book_id == book_id) if book_id is not None else statement
