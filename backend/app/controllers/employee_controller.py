from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.dependencies.authentication import require_roles
from app.models.user import User
from app.schemas.employee_schema import EmployeeCreate, EmployeeResponse
from app.services.employee_service import EmployeeService
from app.repositories.employee_repository import EmployeeRepository
from app.core.database import get_db

router = APIRouter(prefix="/api/v1/employees", tags=["Employees"])

require_administrator = require_roles("ADMINISTRATOR")

def get_employee_service(db: Session = Depends(get_db)) -> EmployeeService:
    return EmployeeService(db=db, employee_repository=EmployeeRepository(db))


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=EmployeeResponse)
def create_employee(
    employee: EmployeeCreate,
    employee_service: EmployeeService = Depends(get_employee_service),
    _current_user: User = Depends(require_administrator),
) -> EmployeeResponse:
    result = employee_service.register(employee)
    return EmployeeResponse(
        id=result.id,
        name=result.name,
        email=result.email,
        role_code=result.role_code,
    )
