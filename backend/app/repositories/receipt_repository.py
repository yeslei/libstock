from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models.domain import Book, Client, Copy, Employee, Loan, Profile, Sale, SaleItem
from app.models.user import User


class ReceiptRepository:
    """Leituras dos comprovantes: fatos persistidos, sem escrita e sem regra de apresentação."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def is_active_employee(self, actor_id: int) -> bool:
        return self.db.scalar(
            select(Employee.id)
            .join(Profile, Profile.id == Employee.id)
            .join(User, User.id == Employee.id)
            .where(Employee.id == actor_id, Profile.is_active.is_(True), User.is_active.is_(True))
        ) is not None

    def find_loan(self, loan_id: int):
        client_user = aliased(User)
        employee_user = aliased(User)
        return self.db.execute(
            select(Loan, Copy, Book, client_user.name.label("client_name"), Client.registration_number,
                   employee_user.name.label("employee_name"), Employee.employee_code)
            .join(Copy, Copy.id == Loan.copy_id)
            .join(Book, Book.id == Copy.book_id)
            .join(Client, Client.id == Loan.client_id)
            .join(client_user, client_user.id == Client.id)
            .join(Employee, Employee.id == Loan.employee_id)
            .join(employee_user, employee_user.id == Employee.id)
            .where(Loan.id == loan_id)
        ).one_or_none()

    def find_sale(self, sale_id: int):
        return self.db.scalar(select(Sale).where(Sale.id == sale_id))

    def sale_parties(self, sale: Sale):
        employee = self.db.execute(
            select(User.name, Employee.employee_code).join(Employee, Employee.id == User.id)
            .where(Employee.id == sale.employee_id)
        ).one()
        client_name = None
        if sale.client_id is not None:
            client_name = self.db.scalar(select(User.name).where(User.id == sale.client_id))
        return employee, client_name

    def sale_items(self, sale_id: int):
        return self.db.execute(
            select(SaleItem, Copy, Book)
            .join(Copy, Copy.id == SaleItem.copy_id)
            .join(Book, Book.id == Copy.book_id)
            .where(SaleItem.sale_id == sale_id)
            .order_by(SaleItem.id)
        ).all()
