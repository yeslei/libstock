from datetime import date

from fastapi import APIRouter, Depends, Query

from app.dependencies.authentication import require_roles
from app.dependencies.services import get_audit_log_service
from app.models.user import User
from app.schemas.audit_log_schema import AuditLogPage
from app.services.audit_log_service import AuditLogService


router = APIRouter(prefix="/api/v1/audit-logs", tags=["Auditoria"])

# A auditoria expõe valores anteriores e novos de obras, exemplares e contas:
# somente o administrador pode consultar.
require_administrator = require_roles("ADMINISTRATOR")


@router.get("", response_model=AuditLogPage)
def list_audit_logs(
    entity_type: str | None = Query(default=None, max_length=100),
    entity_id: str | None = Query(default=None, max_length=100),
    operation: str | None = Query(default=None, max_length=100),
    employee_id: int | None = Query(default=None, ge=1, le=2**31 - 1),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _current_user: User = Depends(require_administrator),
    audit_service: AuditLogService = Depends(get_audit_log_service),
) -> AuditLogPage:
    return audit_service.list_logs(
        entity_type=entity_type,
        entity_id=entity_id,
        operation=operation,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
