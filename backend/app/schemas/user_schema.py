from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import AccountType


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    account_type: AccountType

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("O nome deve possuir pelo menos 2 caracteres.")
        return normalized


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    account_type: AccountType
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
