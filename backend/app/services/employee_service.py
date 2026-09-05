from app.models.user import User
from app.repositories.employee_repository import EmployeeRepository
from app.schemas.employee_schema import EmployeeCreate

class EmployeeService:
    def __init__(self, employee_repository: EmployeeRepository) -> None:
        self.repository = employee_repository

    def register(self, data_in: EmployeeCreate) -> User:
        return self.repository.create(data_in)