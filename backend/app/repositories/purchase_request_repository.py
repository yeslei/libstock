from sqlalchemy import select
from app.models.domain import Copy, DestinationType, PurchaseReservation, ReservationStatus
from datetime import datetime, timezone
from app.core.business_dates import reservation_pickup_deadline
from app.models.purchase_request import PurchaseRequest
from app.repositories.client_request_repository import ClientRequestRepository
from app.repositories.inventory_availability import free_copies_statement


class PurchaseRequestRepository(ClientRequestRepository):
    def find_pending(self, client_id: int, book_id: int):
        return self.db.scalar(select(PurchaseRequest.id).join(PurchaseReservation, PurchaseReservation.id == PurchaseRequest.reservation_id).where(
            PurchaseRequest.client_id == client_id, PurchaseRequest.book_id == book_id,
            PurchaseReservation.status.in_([ReservationStatus.WAITING, ReservationStatus.NOTIFIED])))

    def lock_available_copy(self, book_id: int):
        return self.db.scalar(free_copies_statement(book_id).where(Copy.destination == DestinationType.COMMERCIAL)
                              .order_by(Copy.id).limit(1).with_for_update())

    def has_waiting_queue(self, book_id):
        return self.db.scalar(select(PurchaseReservation.id).where(
            PurchaseReservation.book_id == book_id,
            PurchaseReservation.status == ReservationStatus.WAITING,
        ).limit(1)) is not None

    def create(self, client_id, book_id, pickup_date, copy_id):
        notified_at = datetime.now(timezone.utc)
        reservation = PurchaseReservation(book_id=book_id, client_id=client_id, status=ReservationStatus.NOTIFIED,
            allocated_copy_id=copy_id, notified_at=notified_at,
            expires_at=reservation_pickup_deadline(notified_at))
        self.db.add(reservation); self.db.flush(); self.db.refresh(reservation)
        request = PurchaseRequest(client_id=client_id, book_id=book_id, pickup_date=pickup_date,
                                  status='PENDING', reservation_id=reservation.id)
        self.db.add(request)
        self.db.flush()
        return request
