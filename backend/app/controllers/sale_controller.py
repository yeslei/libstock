from fastapi import APIRouter, Depends

from app.dependencies.authentication import require_roles
from app.dependencies.services import get_sale_service
from app.models.user import User
from app.schemas.sale_schema import SaleCreate, SaleResponse
from app.services.sale_service import SaleService


router = APIRouter(
    prefix="/api/v1/sales",
    tags=["Vendas"],
)

require_sale_creator = require_roles(
    "SELLER",
    "ADMINISTRATOR",
)


@router.post(
    "/",
    response_model=SaleResponse,
    status_code=201,
)
def create_sale(
    sale_data: SaleCreate,
    current_user: User = Depends(require_sale_creator),
    sale_service: SaleService = Depends(get_sale_service),
) -> SaleResponse:
    return sale_service.create_sale(
        sale_data,
        employee_id=current_user.id,
    )