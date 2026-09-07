from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ApplicationError,
    DuplicateEmailError,
    DuplicateEmployeeCodeError,
    PersistenceError,
)
from app.repositories.employee_repository import EmployeeCreated, EmployeeRepository
from app.schemas.employee_schema import EmployeeCreate


def _constraint_name(exc: IntegrityError) -> str | None:
    """Return the violated constraint name from driver diagnostics, or None."""
    orig = exc.orig
    diag = getattr(orig, "diag", None)
    if diag is not None:
        return getattr(diag, "constraint_name", None)
    # Fallback for drivers without diag (e.g. SQLite in tests)
    return None


class EmployeeService:
    def __init__(self, db: Session, employee_repository: EmployeeRepository) -> None:
        self.db = db
        self.repository = employee_repository

    def register(self, data_in: EmployeeCreate) -> EmployeeCreated:
        try:
            result = self.repository.create(data_in)
            self.db.commit()
            return result
        except IntegrityError as exc:
            self.db.rollback()
            constraint = _constraint_name(exc)
            if constraint in ("ix_users_email", "uq_users_email", "users_email_key"):
                raise DuplicateEmailError() from exc
            if constraint in ("employees_employee_code_key", "uq_employees_employee_code"):
                raise DuplicateEmployeeCodeError() from exc
            raise PersistenceError() from exc
        except Exception:
            self.db.rollback()
            raise