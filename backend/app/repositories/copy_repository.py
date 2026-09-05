from sqlalchemy.orm import Session
from app.models.domain import Copy
from app.schemas.copy_schema import CopyCreate

class CopyRepository:
    def __init__(self, db: Session):
        self.db = db

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
        self.db.commit()
        self.db.refresh(db_copy)
        return db_copy