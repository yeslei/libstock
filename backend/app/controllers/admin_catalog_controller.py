from fastapi import APIRouter, Depends, status

from app.dependencies.authentication import require_roles
from app.dependencies.services import get_catalog_service
from app.models.user import User
from app.schemas.catalog_schema import (
    CatalogBookResponse,
    FeaturedUpdate,
    GenreCreate,
    GenreResponse,
)
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/api/v1/admin", tags=["Administração do catálogo"])

require_administrator = require_roles("ADMINISTRATOR")


@router.post("/genres", response_model=GenreResponse, status_code=status.HTTP_201_CREATED)
def create_genre(
    payload: GenreCreate,
    catalog_service: CatalogService = Depends(get_catalog_service),
    _: User = Depends(require_administrator),
) -> GenreResponse:
    return GenreResponse.model_validate(catalog_service.create_genre(payload))


@router.patch("/genres/{genre_id}/featured", response_model=GenreResponse)
def set_genre_featured(
    genre_id: int,
    payload: FeaturedUpdate,
    catalog_service: CatalogService = Depends(get_catalog_service),
    _: User = Depends(require_administrator),
) -> GenreResponse:
    genre = catalog_service.set_genre_featured(genre_id=genre_id, data_in=payload)
    return GenreResponse.model_validate(genre)


@router.patch("/books/{book_id}/featured", response_model=CatalogBookResponse)
def set_book_featured(
    book_id: int,
    payload: FeaturedUpdate,
    catalog_service: CatalogService = Depends(get_catalog_service),
    _: User = Depends(require_administrator),
) -> CatalogBookResponse:
    book = catalog_service.set_book_featured(book_id=book_id, data_in=payload)
    return CatalogBookResponse(
        id=book.id,
        title=book.title,
        author=book.author,
        cover_url=book.cover_url,
        genres=[link.genre.name for link in book.genres],
    )
