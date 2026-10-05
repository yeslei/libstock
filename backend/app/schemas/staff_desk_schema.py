"""Contratos de leitura do balcão (funcionário). Somente dados necessários à operação."""
from datetime import date, datetime
from typing import Literal

from decimal import Decimal

from pydantic import BaseModel

from app.models.domain import CopyStatus, DestinationType


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


class StaffClientPendencies(BaseModel):
    client: StaffClient
    overdue_loans: list[StaffLoan]


AllocationBlock = Literal['NOT_FIRST_ELIGIBLE', 'CLIENT_INELIGIBLE', 'NO_FREE_COPY', 'BOOK_INACTIVE']


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


class StaffDashboard(BaseModel):
    active_loans: int
    returns_today: int
    waiting_reservations: int
    pendencies: int


class StaffGenre(BaseModel):
    id: int
    name: str
    slug: str


class StaffCatalogBook(BaseModel):
    """Obra do acervo para consulta do balcão; contagens consideram exemplares ativos e não vendidos."""
    id: int
    title: str
    author: str
    isbn: str | None
    genre: str | None
    # Categorias do catálogo público (book_genres), em ordem alfabética (Issue #174).
    genres: list[StaffGenre] = []
    is_active: bool
    total_copies: int
    didactic_copies: int
    commercial_copies: int
    available_didactic: int = 0
    available_commercial: int = 0
    cover_url: str | None = None


class StaffCatalogCopy(BaseModel):
    id: int
    barcode: str
    destination: DestinationType
    status: CopyStatus
    condition: str | None
    sale_price: Decimal | None
    is_active: bool
    free: bool
    allocated_for_purchase: bool


class StaffCatalogBookDetail(StaffCatalogBook):
    copies: list[StaffCatalogCopy]


SaleBlock = Literal['DIDACTIC', 'NOT_AVAILABLE']


class StaffCopyBook(BaseModel):
    id: int
    title: str
    author: str
    isbn: str | None
    is_active: bool


class StaffCopyLookup(BaseModel):
    """Exemplar localizado por código, ISBN ou título, com a situação de venda decidida no backend."""
    id: int
    barcode: str
    destination: DestinationType
    status: CopyStatus
    condition: str | None
    sale_price: Decimal | None
    book: StaffCopyBook
    free: bool
    free_commercial_copies: int
    sellable: bool
    sale_block_reason: SaleBlock | None


class DashboardMovement(BaseModel):
    date: date
    loans: int
    returns: int


class DashboardCategory(BaseModel):
    name: str
    count: int


class DashboardPopularBook(BaseModel):
    id: int
    title: str
    author: str
    cover_url: str | None
    loans: int
    reservations: int


class DashboardRecentLoan(BaseModel):
    id: int
    book_id: int
    title: str
    client: str
    date: datetime
    due_date: datetime
    returned_at: datetime | None
    status: str


class StaffDashboardOverview(BaseModel):
    loans_today: int
    week: list[DashboardMovement]
    categories: list[DashboardCategory]
    popular: list[DashboardPopularBook]
    recent_loans: list[DashboardRecentLoan]
    recent_returns: list[DashboardRecentLoan]
