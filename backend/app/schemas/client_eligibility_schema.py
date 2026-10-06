from typing import Literal

from pydantic import BaseModel


class EligibilityReason(BaseModel):
    code: Literal["inactive", "penalized", "overdue_loan"]
    message: str


class EligibilityResponse(BaseModel):
    eligible: bool
    reasons: list[EligibilityReason]
