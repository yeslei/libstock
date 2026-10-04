from sqlalchemy.exc import SQLAlchemyError

from app.core.business_dates import BUSINESS_ZONE
from app.core.exceptions import ApplicationError
from app.models.domain import LoanStatus, SaleStatus
from app.repositories.receipt_repository import ReceiptRepository
from app.schemas.receipt_schema import (
    LoanReceipt, ReceiptBook, ReceiptPerson, ReturnReceipt, SaleReceipt, SaleReceiptItem,
)

STAFF_ROLES = {"SELLER", "ADMINISTRATOR"}


def _not_found() -> ApplicationError:
    return ApplicationError("Comprovante não encontrado.", "receipt_not_found", 404)


class ReceiptService:
    """Comprovantes somente leitura (Issue #152).

    Funcionário ativo (SELLER/ADMINISTRATOR) lê qualquer comprovante; o cliente
    só os próprios. Para o cliente, registro alheio e inexistente são
    indistinguíveis (404), sem vazar existência.
    """

    def __init__(self, db, repository: ReceiptRepository) -> None:
        self.db = db
        self.repository = repository

    def _scope(self, user):
        """Devolve o client_id restrito, ou None quando o ator é funcionário ativo."""
        if set(user.role_codes) & STAFF_ROLES:
            if not self.repository.is_active_employee(user.id):
                raise ApplicationError(
                    "Cadastro de funcionário ativo necessário.", "employee_record_required", 403)
            return None
        return user.id

    def _read(self, query):
        try:
            return query()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ApplicationError(
                "Não foi possível consultar o comprovante.", "receipt_query_error", 500) from exc

    @staticmethod
    def _loan_fields(row) -> dict:
        loan, copy, book, client_name, registration, employee_name, employee_code = row
        return dict(
            number=loan.id,
            client=ReceiptPerson(id=loan.client_id, name=client_name, code=registration),
            employee=ReceiptPerson(id=loan.employee_id, name=employee_name, code=employee_code),
            book=ReceiptBook(title=book.title, author=book.author, isbn=book.isbn),
            copy_id=copy.id, copy_barcode=copy.barcode,
            loan_date=loan.loan_date, due_date=loan.due_date,
        )

    def _find_loan(self, loan_id: int, user):
        scope = self._scope(user)
        row = self._read(lambda: self.repository.find_loan(loan_id))
        if row is None or row[0].status == LoanStatus.CANCELLED:
            raise _not_found()
        if scope is not None and row[0].client_id != scope:
            raise _not_found()
        return row

    def loan_receipt(self, loan_id: int, user) -> LoanReceipt:
        return LoanReceipt(**self._loan_fields(self._find_loan(loan_id, user)))

    def return_receipt(self, loan_id: int, user) -> ReturnReceipt:
        row = self._find_loan(loan_id, user)
        loan = row[0]
        if loan.status != LoanStatus.RETURNED or loan.returned_at is None:
            raise ApplicationError("Empréstimo ainda não foi devolvido.", "loan_not_returned", 409)
        due = loan.due_date.astimezone(BUSINESS_ZONE).date()
        returned = loan.returned_at.astimezone(BUSINESS_ZONE).date()
        return ReturnReceipt(**self._loan_fields(row), returned_at=loan.returned_at,
                             days_late=max(0, (returned - due).days))

    def sale_receipt(self, sale_id: int, user) -> SaleReceipt:
        scope = self._scope(user)
        sale = self._read(lambda: self.repository.find_sale(sale_id))
        if sale is None or sale.status != SaleStatus.CONFIRMED:
            raise _not_found()
        if scope is not None and sale.client_id != scope:
            raise _not_found()
        employee, client_name = self._read(lambda: self.repository.sale_parties(sale))
        items = self._read(lambda: self.repository.sale_items(sale.id))
        return SaleReceipt(
            number=sale.id,
            client=None if sale.client_id is None else ReceiptPerson(id=sale.client_id, name=client_name),
            employee=ReceiptPerson(id=sale.employee_id, name=employee.name, code=employee.employee_code),
            sale_date=sale.sale_date,
            items=[SaleReceiptItem(copy_id=copy.id, copy_barcode=copy.barcode,
                                   book=ReceiptBook(title=book.title, author=book.author, isbn=book.isbn),
                                   unit_price=item.unit_price)
                   for item, copy, book in items],
            total_amount=sale.total_amount,
        )
