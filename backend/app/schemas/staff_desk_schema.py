"""Contratos de leitura do balcão (funcionário). Somente dados necessários à operação."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class StaffClient(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool
    is_penalized: bool
    has_overdue_loan: bool
    eligible: bool


class StaffBook(BaseModel):
    id: int
    title: str
    author: str
    is_active: bool


class EligibleCopy(BaseModel):
    id: int
    barcode: str
    condition: str | None


class StaffLoanRequest(BaseModel):
    id: int
    client: StaffClient
    book: StaffBook
    pickup_date: date
    due_date: date
    created_at: datetime
    eligible_copies: list[EligibleCopy]


class StaffLoan(BaseModel):
    id: int
    client: StaffClient
    book: StaffBook
    copy_id: int
    copy_barcode: str
    loan_date: datetime
    due_date: datetime
    status: Literal['ACTIVE', 'OVERDUE']
    days_late: int


AllocationBlock = Literal['NOT_FIRST_IN_QUEUE', 'CLIENT_INELIGIBLE', 'NO_FREE_COPY', 'BOOK_INACTIVE']


class StaffPurchaseReservation(BaseModel):
    id: int
    client: StaffClient
    book: StaffBook
    status: Literal['WAITING', 'NOTIFIED']
    queue_position: int | None
    requested_at: datetime
    pickup_date: date | None
    notified_at: datetime | None
    expires_at: datetime | None
    expired: bool
    allocated_copy_id: int | None
    allocated_copy_barcode: str | None
    free_commercial_copies: int
    can_allocate: bool
    allocation_blocked_reason: AllocationBlock | None
