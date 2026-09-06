from fastapi import APIRouter, Depends, status

from app.dependencies.authentication import get_current_user, require_roles
from app.dependencies.services import get_user_service
from app.models.user import User
from app.schemas.user_schema import UserInactivateResponse, UserResponse
from app.services.user_service import UserService


router = APIRouter(prefix="/api/v1/users", tags=["Usuários"])

require_administrator = require_roles("ADMINISTRATOR")


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch(
    "/{user_id}/inactivate",
    response_model=UserInactivateResponse,
    status_code=status.HTTP_200_OK,
)
def inactivate_user(
    user_id: int,
    current_user: User = Depends(require_administrator),
    user_service: UserService = Depends(get_user_service),
) -> User:
    return user_service.inactivate_user(user_id, actor_id=current_user.id)
