from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.business_dates import BUSINESS_ZONE
from app.models.domain import AuditLog
from app.models.user import User


class AuditLogRepository:
    """Consultas de leitura sobre `audit_logs`; a tabela não aceita UPDATE nem DELETE."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_entries(
        self,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        operation: str | None = None,
        employee_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[AuditLog, str | None]], int]:
        conditions = []
        if entity_type is not None:
            conditions.append(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            conditions.append(AuditLog.entity_id == entity_id)
        if operation is not None:
            conditions.append(AuditLog.operation == operation)
        if employee_id is not None:
            conditions.append(AuditLog.employee_id == employee_id)
        if date_from is not None:
            conditions.append(AuditLog.occurred_at >= _start_of_day(date_from))
        if date_to is not None:
            conditions.append(AuditLog.occurred_at < _start_of_day(date_to + timedelta(days=1)))

        total = self.db.scalar(
            select(func.count()).select_from(AuditLog).where(*conditions)
        ) or 0
        statement = (
            select(AuditLog, User.name)
            .outerjoin(User, User.id == AuditLog.employee_id)
            .where(*conditions)
            .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.execute(statement).all()), total


def _start_of_day(day: date) -> datetime:
    """Início do dia no fuso de negócio (America/Sao_Paulo), como nas demais regras."""
    return datetime.combine(day, time.min, tzinfo=BUSINESS_ZONE)
