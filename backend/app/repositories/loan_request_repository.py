from datetime import date

from sqlalchemy import select

from app.models.domain import Copy, DestinationType
from app.models.loan_request import LoanRequest


from app.repositories.inventory_availability import free_copies_statement
from app.repositories.client_request_repository import ClientRequestRepository


class LoanRequestRepository(ClientRequestRepository):
    def find_pending(self, client_id: int, book_id: int):
        return self.db.scalar(select(LoanRequest.id).where(
            LoanRequest.client_id == client_id, LoanRequest.book_id == book_id, LoanRequest.loan_id.is_(None)))

    def lock_available_copy(self, book_id: int):
        return self.db.scalar(free_copies_statement(book_id).where(Copy.destination == DestinationType.DIDACTIC)
                              .order_by(Copy.id).limit(1).with_for_update())

    def create(self, client_id: int, book_id: int, pickup_date: date, due_date: date):
        request = LoanRequest(client_id=client_id, book_id=book_id, pickup_date=pickup_date,
                              due_date=due_date, status="PENDING")
        self.db.add(request)
        self.db.flush()
        return request
