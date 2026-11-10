from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.authentication import require_roles
from app.models.user import User
from app.schemas.notification_schema import NotificationPage, NotificationResponse
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/v1/me/notifications", tags=["Notificações do cliente"])


def get_notification_service(db: Session = Depends(get_db)) -> NotificationService:
    return NotificationService(db)


@router.get("", response_model=NotificationPage)
def list_notifications(
    before_id: Annotated[int | None, Query(gt=0, le=2**63 - 1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    user: User = Depends(require_roles("USER")),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationPage:
    return service.list_own(user.id, before_id=before_id, limit=limit)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: Annotated[int, Path(gt=0, le=2**63 - 1)],
    user: User = Depends(require_roles("USER")),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationResponse:
    return service.mark_read(user.id, notification_id)
