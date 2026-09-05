from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.employee_schema import EmployeeCreate

class EmployeeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data_in: EmployeeCreate) -> User:
        # Futura implementação de persistência com SQLAlchemy
        pass