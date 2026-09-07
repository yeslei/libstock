from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.models.domain import Copy, Employee
from app.schemas.copy_schema import CopyCreate

class CopyRepository:
    def __init__(self, db: Session):
        self.db = db

    def is_employee(self, user_id: int) -> bool:
        return self.db.scalar(select(Employee.id).where(Employee.id == user_id)) is not None

    def set_audit_actor(self, employee_id: int) -> None:
        self.db.execute(
            text("SELECT set_config('libstock.employee_id', :valor, true)"),
            {"valor": str(employee_id)},
        )

    def create_copy(self, copy_data: CopyCreate) -> Copy:
        db_copy = Copy(
            book_id=copy_data.book_id,
            barcode=copy_data.barcode,
            destination=copy_data.destination,
            condition=copy_data.condition,
            sale_price=copy_data.sale_price,
            acquired_at=copy_data.acquired_at,
        )
        self.db.add(db_copy)
        self.db.flush()
        self.db.refresh(db_copy)
        return db_copy
