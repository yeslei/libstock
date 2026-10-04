from sqlalchemy import select, text
from app.models.domain import AuditLog, Client, Copy, Loan, PurchaseReservation, ReservationStatus, Sale, SaleItem, SaleStatus
from app.models.loan_request import LoanRequest
from app.repositories.client_request_repository import ClientRequestRepository
from app.repositories.inventory_availability import free_copies_statement


class CirculationRepository(ClientRequestRepository):
    def set_audit_actor(self, actor_id):
        self.db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(actor_id)})

    def find_request(self, request_id, *, lock=False):
        statement = select(LoanRequest).where(LoanRequest.id == request_id)
        return self.db.scalar((statement.with_for_update() if lock else statement).execution_options(populate_existing=True))

    def find_loan(self, loan_id):
        return self.db.scalar(select(Loan).where(Loan.id == loan_id).with_for_update())

    def find_reservation(self, reservation_id, *, lock=False):
        statement = select(PurchaseReservation).where(PurchaseReservation.id == reservation_id)
        return self.db.scalar((statement.with_for_update() if lock else statement).execution_options(populate_existing=True))

    def waiting_queue(self, book_id):
        """WAITING reservations of the book in queue order, locked; ineligible ones keep their position."""
        return self.db.scalars(select(PurchaseReservation).where(
            PurchaseReservation.book_id == book_id, PurchaseReservation.status == ReservationStatus.WAITING,
        ).order_by(PurchaseReservation.queue_position, PurchaseReservation.id).with_for_update()
            .execution_options(populate_existing=True)).all()

    def client_exists(self, client_id):
        return self.db.scalar(select(Client.id).where(Client.id == client_id)) is not None

    def record_cancellation(self, reservation_id, actor_user_id, actor_role, reason):
        """Explicit audit entry with the actor (a client has no employee id, so it goes in new_value)."""
        self.db.add(AuditLog(employee_id=actor_user_id if actor_role == 'STAFF' else None,
                             entity_type='purchase_reservations', entity_id=str(reservation_id), operation='CANCEL',
                             new_value={'actor_user_id': actor_user_id, 'actor_role': actor_role, 'reason': reason}))
        self.db.flush()

    def lock_free_copy(self, book_id, destination, copy_id=None):
        statement = free_copies_statement(book_id).where(Copy.destination == destination)
        if copy_id is not None:
            statement = statement.where(Copy.id == copy_id)
        return self.db.scalar(statement.order_by(Copy.id).limit(1).with_for_update())

    def lock_allocated_copy(self, copy_id):
        return self.db.scalar(select(Copy).where(Copy.id == copy_id)
            .with_for_update().execution_options(populate_existing=True))

    def create_loan(self, **values):
        loan = Loan(**values)
        self.db.add(loan)
        self.db.flush()
        return loan

    def flush(self):
        self.db.flush()

    def create_sale(self, client_id, actor_id, copy):
        sale = Sale(client_id=client_id, employee_id=actor_id, status=SaleStatus.PENDING)
        self.db.add(sale)
        self.db.flush()
        self.db.add(SaleItem(sale_id=sale.id, copy_id=copy.id, unit_price=copy.sale_price))
        self.db.flush()
        return sale
