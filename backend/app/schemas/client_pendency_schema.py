from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


PenaltyAction = Literal["APPLY", "REMOVE"]


class OverdueLoanResponse(BaseModel):
    loan_id: int
    copy_id: int
    book_id: int
    book_title: str
    loan_date: datetime
    due_date: datetime


class ClientPendencyResponse(BaseModel):
    client_id: int
    has_pending: bool
    is_penalized: bool
    overdue_loans: list[OverdueLoanResponse] = Field(default_factory=list)


class ClientPenaltyUpdate(BaseModel):
    action: PenaltyAction
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = " ".join(value.split())

        if len(normalized) < 3:
            raise ValueError("O motivo deve possuir pelo menos 3 caracteres.")

        return normalized

class ClientValidationResponse(BaseModel):
    client_id: int
    valid: bool


# Compatibilidade com o nome usado pelo contrato inicial da feature.
PenaltyUpdateRequest = ClientPenaltyUpdate
