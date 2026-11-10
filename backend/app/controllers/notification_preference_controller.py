from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.authentication import require_roles
from app.models.user import User
from app.repositories.notification_preference_repository import NotificationPreferenceRepository
from app.schemas.notification_preference_schema import (
    NotificationPreferenceResponse, NotificationPreferenceUpdate,
)
from app.services.notification_preference_service import NotificationPreferenceService

router = APIRouter(prefix="/api/v1/me/notification-preferences", tags=["Notificações do cliente"])


def get_notification_preference_service(db: Session = Depends(get_db)) -> NotificationPreferenceService:
    return NotificationPreferenceService(db, NotificationPreferenceRepository(db))


@router.get("", response_model=NotificationPreferenceResponse)
def get_preferences(
    user: User = Depends(require_roles("USER")),
    service: NotificationPreferenceService = Depends(get_notification_preference_service),
) -> NotificationPreferenceResponse:
    return service.get(user.id)


@router.patch("", response_model=NotificationPreferenceResponse)
def update_preferences(
    data: NotificationPreferenceUpdate,
    user: User = Depends(require_roles("USER")),
    service: NotificationPreferenceService = Depends(get_notification_preference_service),
) -> NotificationPreferenceResponse:
    return service.update(user.id, data)
