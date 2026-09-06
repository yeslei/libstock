from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.schemas.employee_schema import EmployeeCreate
from app.services.employee_service import EmployeeService
from app.repositories.employee_repository import EmployeeRepository
from app.core.database import get_db
from app.dependencies.authentication import require_roles
from app.models.user import User

router = APIRouter(prefix="/api/v1/employees", tags=["Employees"])

# RF06: cadastrar funcionário define nível de acesso, então é operação
# privativa do administrador. A rota estava aberta.
require_administrator = require_roles("ADMINISTRATOR")

def get_employee_service(db: Session = Depends(get_db)) -> EmployeeService:
    repository = EmployeeRepository(db)
    return EmployeeService(repository)

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_employee(
    employee: EmployeeCreate,
    employee_service: EmployeeService = Depends(get_employee_service),
    _: User = Depends(require_administrator),
):
    return {
        "message": "Cadastro processado com sucesso. Integração com o banco pendente.",
        "employee_data": {
            "name": employee.name,
            "email": employee.email,
            "accessLevel": employee.accessLevel
        }
    }