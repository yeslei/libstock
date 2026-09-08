from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


RoleCode = Literal["USER", "SELLER", "STOCK_KEEPER", "ADMINISTRATOR"]


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

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
    role_codes: list[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserInactivateResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    is_active: bool
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserAdminResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role_codes: list[RoleCode]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    email: EmailStr | None = None
    role_code: RoleCode | None = None

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("O nome deve possuir pelo menos 2 caracteres.")
        return normalized

    @model_validator(mode="after")
    def require_change(self) -> "UserUpdate":
        if self.name is None and self.email is None and self.role_code is None:
            raise ValueError("Informe ao menos um campo para atualização.")
        return self
