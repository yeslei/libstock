from app.core.exceptions import InactiveUserError, UserNotFoundError
from app.models.user import User
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    def get_by_id(self, user_id: int) -> User:
        user = self.user_repository.find_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        profile = self.user_repository.find_profile_by_user_id(user_id)
        if profile is not None and not profile.is_active:
            raise InactiveUserError()
        return user
