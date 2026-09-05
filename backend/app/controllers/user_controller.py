from fastapi import APIRouter, Depends

from app.dependencies.authentication import get_current_user
from app.models.user import User
from app.schemas.user_schema import UserResponse


router = APIRouter(prefix="/api/v1/users", tags=["Usuários"])


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
