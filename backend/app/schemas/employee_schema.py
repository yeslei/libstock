from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

# Códigos canônicos aceitos, derivados das migrations aplicadas.
VALID_ROLE_CODES: frozenset[str] = frozenset({
    "ATTENDANT",
    "SELLER",
    "STOCK_KEEPER",
    "MANAGER",
})
EmployeeRoleCode = Literal["ATTENDANT", "SELLER", "STOCK_KEEPER", "MANAGER"]


class EmployeeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    accessLevel: EmployeeRoleCode

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("O nome deve possuir pelo menos 2 caracteres.")
        return normalized

class EmployeeResponse(BaseModel):
    id: int
    name: str
    email: str
    role_code: str

    model_config = {"from_attributes": True}