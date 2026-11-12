from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditLogItem(BaseModel):
    """Uma linha imutável de `audit_logs`, já com o nome do funcionário resolvido."""

    id: int
    occurred_at: datetime
    employee_id: int | None
    employee_name: str | None
    entity_type: str
    entity_id: str
    operation: str
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None


class AuditLogPage(BaseModel):
    items: list[AuditLogItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
