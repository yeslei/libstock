from sqlalchemy import select, func
from app.models.domain import Book, Client, Copy, Loan, LoanStatus, PurchaseReservation, ReservationStatus
from app.models.loan_request import LoanRequest
from app.repositories.client_request_repository import ClientRequestRepository
from app.repositories.inventory_availability import free_copies_statement, reservable_commercial_statement
from app.models.domain import DestinationType


class ClientTrackingRepository(ClientRequestRepository):
    def client_exists(self, client_id):
        return self.db.scalar(select(Client.id).where(Client.id == client_id)) is not None

    def pending_loans(self, client_id):
        return self.db.execute(select(LoanRequest, Book).join(Book, Book.id == LoanRequest.book_id)
                               .where(LoanRequest.client_id == client_id, LoanRequest.loan_id.is_(None))
                               .order_by(LoanRequest.created_at, LoanRequest.id)).all()

    def active_loans(self, client_id):
        return self.db.execute(select(Loan, Copy, Book).join(Copy, Copy.id == Loan.copy_id)
                               .join(Book, Book.id == Copy.book_id)
                               .where(Loan.client_id == client_id, Loan.status == LoanStatus.OPEN)
                               .order_by(Loan.due_date, Loan.id)).all()

    def active_reservations(self, client_id):
        return self.db.execute(select(PurchaseReservation, Book, Copy)
                               .join(Book, Book.id == PurchaseReservation.book_id)
                               .outerjoin(Copy, Copy.id == PurchaseReservation.allocated_copy_id)
                               .where(PurchaseReservation.client_id == client_id,
                                      PurchaseReservation.status.in_([ReservationStatus.WAITING, ReservationStatus.NOTIFIED]))
                               .order_by(PurchaseReservation.requested_at, PurchaseReservation.id)).all()

    def waiting_position(self, reservation):
        return 1 + (self.db.scalar(select(func.count()).select_from(PurchaseReservation).where(
            PurchaseReservation.book_id == reservation.book_id, PurchaseReservation.status == ReservationStatus.WAITING,
            PurchaseReservation.queue_position < reservation.queue_position)) or 0)

    def existing_reservation(self, client_id, book_id):
        return self.db.scalar(select(PurchaseReservation).where(PurchaseReservation.client_id == client_id,
            PurchaseReservation.book_id == book_id, PurchaseReservation.status.in_([ReservationStatus.WAITING, ReservationStatus.NOTIFIED])))

    def has_reservable_commercial_copy(self, book_id):
        return self.db.scalar(reservable_commercial_statement(book_id).limit(1)) is not None

    def has_free_commercial_copy(self, book_id):
        return self.db.scalar(free_copies_statement(book_id).where(
            Copy.destination == DestinationType.COMMERCIAL,
        ).limit(1)) is not None

    def create_reservation(self, client_id, book_id):
        reservation = PurchaseReservation(book_id=book_id, client_id=client_id, status=ReservationStatus.WAITING)
        self.db.add(reservation)
        self.db.flush()
        self.db.refresh(reservation)
        return reservation
