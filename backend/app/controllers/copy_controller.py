from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.schemas.copy_schema import (
    CopyBatchCreate,
    CopyCreate,
    CopyDeleteResponse,
    CopyResponse,
)
from app.services.copy_service import CopyService
from app.repositories.copy_repository import CopyRepository
from app.core.database import get_db
from app.dependencies.authentication import require_roles
from app.models.user import User

router = APIRouter(prefix="/api/v1/copies", tags=["Copies"])

def get_copy_service(db: Session = Depends(get_db)) -> CopyService:
    repository = CopyRepository(db)
    return CopyService(repository, db)

@router.post(
    "/batch",
    response_model=list[CopyResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_copies_batch(
    copies: CopyBatchCreate,
    copy_service: CopyService = Depends(get_copy_service),
    current_user: User = Depends(
        require_roles("STOCK_KEEPER", "ADMINISTRATOR")
    ),
):
    return copy_service.create_copies(
        copies_data=copies,
        actor_id=current_user.id,
    )

@router.post("/", response_model=CopyResponse, status_code=status.HTTP_201_CREATED)
def create_copy(
    copy: CopyCreate,
    copy_service: CopyService = Depends(get_copy_service),
    current_user: User = Depends(
        require_roles("STOCK_KEEPER", "ADMINISTRATOR")
    ),
):
    return copy_service.create_new_copy(copy_data=copy, actor_id=current_user.id)


@router.delete("/{copy_id}", response_model=CopyDeleteResponse)
def delete_copy(
    copy_id: int,
    copy_service: CopyService = Depends(get_copy_service),
    current_user: User = Depends(
        require_roles("STOCK_KEEPER", "ADMINISTRATOR")
    ),
):
    return copy_service.delete_copy(copy_id=copy_id, actor_id=current_user.id)
