from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.schemas.copy_schema import CopyCreate, CopyResponse
from app.services.copy_service import CopyService
from app.repositories.copy_repository import CopyRepository
from app.core.database import get_db

router = APIRouter(prefix="/api/v1/copies", tags=["Copies"])

def get_copy_service(db: Session = Depends(get_db)) -> CopyService:
    repository = CopyRepository(db)
    return CopyService(repository)

@router.post("/", response_model=CopyResponse, status_code=status.HTTP_201_CREATED)
def create_copy(
    copy: CopyCreate,
    copy_service: CopyService = Depends(get_copy_service)
):
    return copy_service.create_new_copy(copy_data=copy)