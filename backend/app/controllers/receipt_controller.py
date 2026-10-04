from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.authentication import require_roles
from app.models.user import User
from app.repositories.receipt_repository import ReceiptRepository
from app.schemas.receipt_schema import LoanReceipt, ReturnReceipt, SaleReceipt
from app.services.receipt_service import ReceiptService

router = APIRouter(prefix="/api/v1/receipts", tags=["Comprovantes"])
ResourceId = Annotated[int, Path(gt=0, le=2**63 - 1)]
receipt_reader = require_roles("USER", "SELLER", "ADMINISTRATOR")


def get_receipt_service(db: Session = Depends(get_db)) -> ReceiptService:
    return ReceiptService(db, ReceiptRepository(db))


@router.get("/loans/{loan_id}", response_model=LoanReceipt)
def loan_receipt(loan_id: ResourceId, user: User = Depends(receipt_reader),
                 service: ReceiptService = Depends(get_receipt_service)) -> LoanReceipt:
    return service.loan_receipt(loan_id, user)


@router.get("/returns/{loan_id}", response_model=ReturnReceipt)
def return_receipt(loan_id: ResourceId, user: User = Depends(receipt_reader),
                   service: ReceiptService = Depends(get_receipt_service)) -> ReturnReceipt:
    return service.return_receipt(loan_id, user)


@router.get("/sales/{sale_id}", response_model=SaleReceipt)
def sale_receipt(sale_id: ResourceId, user: User = Depends(receipt_reader),
                 service: ReceiptService = Depends(get_receipt_service)) -> SaleReceipt:
    return service.sale_receipt(sale_id, user)
