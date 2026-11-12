from datetime import date

from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import ApplicationError
from app.repositories.audit_log_repository import AuditLogRepository
from app.schemas.audit_log_schema import AuditLogItem, AuditLogPage

MAX_LIMIT = 100


class AuditLogService:
    """Leitura de auditoria; não existe operação de escrita, edição ou exclusão."""

    def __init__(self, db, repository: AuditLogRepository) -> None:
        self.db = db
        self.repository = repository

    def list_logs(
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
    ) -> AuditLogPage:
        if not 1 <= limit <= MAX_LIMIT:
            raise ApplicationError(
                f"O limite deve estar entre 1 e {MAX_LIMIT}.",
                "invalid_pagination",
                422,
            )
        if offset < 0:
            raise ApplicationError(
                "O deslocamento não pode ser negativo.",
                "invalid_pagination",
                422,
            )
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ApplicationError(
                "A data inicial não pode ser posterior à data final.",
                "invalid_date_range",
                422,
            )

        rows, total = self._read(
            lambda: self.repository.list_entries(
                entity_type=_normalize(entity_type),
                entity_id=_normalize(entity_id),
                operation=_normalize(operation),
                employee_id=employee_id,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                offset=offset,
            )
        )
        items = [
            AuditLogItem(
                id=entry.id,
                occurred_at=entry.occurred_at,
                employee_id=entry.employee_id,
                employee_name=employee_name,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                operation=entry.operation,
                old_value=entry.old_value,
                new_value=entry.new_value,
            )
            for entry, employee_name in rows
        ]
        return AuditLogPage(items=items, total=total, limit=limit, offset=offset)

    def _read(self, query):
        try:
            return query()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ApplicationError(
                "Não foi possível consultar os logs de auditoria.",
                "audit_log_query_error",
                500,
            ) from exc


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
