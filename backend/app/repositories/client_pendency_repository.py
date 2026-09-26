from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.domain import AuditLog, Book, Client, Copy, Employee, Loan, LoanStatus

from app.models.domain import (
    AuditLog,
    Book,
    Client,
    Copy,
    Employee,
    Loan,
    LoanStatus,
)
from app.models.user import User

class ClientPendencyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_client_for_update(self, client_id: int) -> Client | None:
        statement = (
            select(Client)
            .where(Client.id == client_id)
            .with_for_update()
        )
        return self.db.scalar(statement)

    def list_overdue_loans(self, client_id: int) -> list[dict]:
        statement = (
            select(
                Loan.id.label("loan_id"),
                Loan.copy_id.label("copy_id"),
                Copy.book_id.label("book_id"),
                Book.title.label("book_title"),
                Loan.loan_date.label("loan_date"),
                Loan.due_date.label("due_date"),
            )
            .join(Copy, Copy.id == Loan.copy_id)
            .join(Book, Book.id == Copy.book_id)
            .where(
                Loan.client_id == client_id,
                Loan.status == LoanStatus.OPEN,
                Loan.returned_at.is_(None),
                Loan.due_date < func.now(),
            )
            .order_by(Loan.due_date, Loan.id)
        )

        return list(self.db.execute(statement).mappings().all())

    def find_employee_by_id(self, employee_id: int) -> Employee | None:
        return self.db.scalar(
            select(Employee).where(Employee.id == employee_id)
        )

    def update_penalized(
        self,
        client: Client,
        is_penalized: bool,
    ) -> None:
        client.is_penalized = is_penalized
        self.db.flush()

    def record_penalty_change(
        self,
        *,
        client_id: int,
        action: str,
        old_value: bool,
        new_value: bool,
        reason: str,
        actor_type: str,
        employee_id: int | None,
    ) -> None:
        audit_log = AuditLog(
            employee_id=employee_id,
            entity_type="clients",
            entity_id=str(client_id),
            operation=action,
            old_value={
                "is_penalized": old_value,
            },
            new_value={
                "is_penalized": new_value,
                "reason": reason,
                "actor_type": actor_type,
                "actor_id": employee_id,
            },
        )

        self.db.add(audit_log)
        self.db.flush()

    def find_user_active(self, client_id: int) -> bool | None:
        return self.db.scalar(
            select(User.is_active).where(User.id == client_id)
        )