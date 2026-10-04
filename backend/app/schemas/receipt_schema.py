from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ReceiptPerson(BaseModel):
    id: int
    name: str
    code: str | None = None


class ReceiptBook(BaseModel):
    title: str
    author: str
    isbn: str | None = None


class LoanReceipt(BaseModel):
    """Comprovante de empréstimo, montado só com dados persistidos."""

    number: int
    client: ReceiptPerson
    employee: ReceiptPerson
    book: ReceiptBook
    copy_id: int
    copy_barcode: str
    loan_date: datetime
    due_date: datetime


class ReturnReceipt(LoanReceipt):
    """Comprovante de devolução: o empréstimo e a data de devolução gravada."""

    returned_at: datetime
    days_late: int


class SaleReceiptItem(BaseModel):
    copy_id: int
    copy_barcode: str
    book: ReceiptBook
    unit_price: Decimal


class SaleReceipt(BaseModel):
    number: int
    client: ReceiptPerson | None
    employee: ReceiptPerson
    sale_date: datetime
    items: list[SaleReceiptItem]
    total_amount: Decimal
