from fastapi import APIRouter, Depends, Path

from app.dependencies.authentication import require_roles
from app.dependencies.services import get_client_pendency_service
from app.models.user import User
from app.schemas.client_pendency_schema import (
    ClientPenaltyUpdate,
    ClientPendencyResponse,
    ClientValidationResponse,
)
from app.services.client_pendency_service import ClientPendencyService


router = APIRouter(
    prefix="/api/v1/clients",
    tags=["Clientes"],
)

require_pendency_reader = require_roles("SELLER", "ADMINISTRATOR")

@router.get(
    "/{client_id}/validation",
    response_model=ClientValidationResponse,
)
def validate_client(
    client_id: int = Path(gt=0),
    _current_user: User = Depends(require_pendency_reader),
    client_pendency_service: ClientPendencyService = Depends(
        get_client_pendency_service
    ),
) -> ClientValidationResponse:
    return client_pendency_service.validate_client_for_operation(client_id)

@router.get(
    "/{client_id}/pendencies",
    response_model=ClientPendencyResponse,
)
def get_client_pendencies(
    client_id: int = Path(gt=0),
    _current_user: User = Depends(require_pendency_reader),
    client_pendency_service: ClientPendencyService = Depends(
        get_client_pendency_service
    ),
) -> ClientPendencyResponse:
    return client_pendency_service.get_pendencies(client_id)


@router.patch(
    "/{client_id}/penalty",
    response_model=ClientPendencyResponse,
)
def update_client_penalty(
    client_id: int,
    payload: ClientPenaltyUpdate,
    current_user: User = Depends(require_pendency_reader),
    client_pendency_service: ClientPendencyService = Depends(
        get_client_pendency_service
    ),
) -> ClientPendencyResponse:
    return client_pendency_service.change_penalty(
        client_id=client_id,
        action=payload.action,
        reason=payload.reason,
        actor_id=current_user.id,
    )
