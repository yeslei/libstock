from fastapi import APIRouter, Depends

from app.dependencies.authentication import require_roles
from app.dependencies.services import get_loan_service
from app.models.user import User
from app.schemas.loan_schema import LoanCreate, LoanResponse
from app.services.loan_service import LoanService


router = APIRouter(
    prefix="/api/v1/loans",
    tags=["Empréstimos"],
)

require_loan_creator = require_roles(
    "SELLER",
    "ADMINISTRATOR",
)


@router.post(
    "/",
    response_model=LoanResponse,
    status_code=201,
)
def create_loan(
    loan_data: LoanCreate,
    current_user: User = Depends(require_loan_creator),
    loan_service: LoanService = Depends(get_loan_service),
) -> LoanResponse:
    return loan_service.create_loan(
        loan_data,
        employee_id=current_user.id,
    )