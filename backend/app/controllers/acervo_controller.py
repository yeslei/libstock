from fastapi import APIRouter, Depends, status

from app.dependencies.authentication import require_roles
from app.dependencies.services import get_acervo_service
from app.models.user import User
from app.schemas.acervo_schema import (
    AcervoItemResponse,
    ClassifyItemInput,
    DestinationTagResponse,
)
from app.services.acervo_service import AcervoService

router = APIRouter(prefix="/api/v1/acervo", tags=["Gestão do Acervo"])

require_acervo_access = require_roles("STOCK_KEEPER", "ADMINISTRATOR")


@router.get("/tags", response_model=list[DestinationTagResponse])
def list_destination_tags(
    service: AcervoService = Depends(get_acervo_service),
    _: User = Depends(require_acervo_access),
) -> list[DestinationTagResponse]:
    """Lista as tags de destinação disponíveis."""
    tags = service.list_tags()
    return [DestinationTagResponse.model_validate(t) for t in tags]


@router.get("/{item_id}", response_model=AcervoItemResponse)
def get_acervo_item(
    item_id: int,
    service: AcervoService = Depends(get_acervo_service),
    _: User = Depends(require_acervo_access),
) -> AcervoItemResponse:
    """Consulta detalhes e classificação atual de um item do acervo."""
    item = service.get_item(item_id)
    return AcervoItemResponse.model_validate(item)


@router.post("/{item_id}/tags", response_model=AcervoItemResponse, status_code=status.HTTP_200_OK)
def classify_item_tags(
    item_id: int,
    payload: ClassifyItemInput,
    service: AcervoService = Depends(get_acervo_service),
    current_user: User = Depends(require_acervo_access),
) -> AcervoItemResponse:
    """Classifica um item do acervo vinculando uma tag de destinação."""
    item = service.classify_item(item_id, payload, actor_id=current_user.id)
    return AcervoItemResponse.model_validate(item)


@router.patch("/{item_id}/destinacao", response_model=AcervoItemResponse, status_code=status.HTTP_200_OK)
def update_item_destination(
    item_id: int,
    payload: ClassifyItemInput,
    service: AcervoService = Depends(get_acervo_service),
    current_user: User = Depends(require_acervo_access),
) -> AcervoItemResponse:
    """Atualiza a classificação de destinação de um item do acervo."""
    item = service.classify_item(item_id, payload, actor_id=current_user.id)
    return AcervoItemResponse.model_validate(item)

