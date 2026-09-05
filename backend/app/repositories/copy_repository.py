from sqlalchemy.orm import Session
from app.models.domain import Copy
from app.schemas.copy_schema import CopyCreate

class CopyRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_copy(self, copy_data: CopyCreate) -> Copy:
        db_copy = Copy(
            barcode=copy_data.barcode,
            destinationTag=copy_data.destinationTag,
            book_id=copy_data.book_id,
            status="Available"
        )
        self.db.add(db_copy)
        self.db.commit()
        self.db.refresh(db_copy)
        return db_copy