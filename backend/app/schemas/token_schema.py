from pydantic import BaseModel

from app.schemas.user_schema import UserResponse


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
