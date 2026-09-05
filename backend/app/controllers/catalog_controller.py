from fastapi import APIRouter, Depends, Query

from app.dependencies.services import get_catalog_service
from app.schemas.catalog_schema import (
    CatalogBookResponse,
    GenreResponse,
    PagedBooksResponse,
)
from app.services.catalog_service import CatalogService

# Rotas públicas: a vitrine é navegável sem sessão. O login só é exigido nas
# ações transacionais, que vivem fora deste controller.
router = APIRouter(prefix="/api/v1/catalog", tags=["Catálogo"])


@router.get("/featured-books", response_model=list[CatalogBookResponse])
def list_featured_books(
    catalog_service: CatalogService = Depends(get_catalog_service),
) -> list[CatalogBookResponse]:
    return catalog_service.list_featured_books()


@router.get("/genres", response_model=list[GenreResponse])
def list_featured_genres(
    catalog_service: CatalogService = Depends(get_catalog_service),
) -> list[GenreResponse]:
    return catalog_service.list_featured_genres()


@router.get("/genres/{slug}/books", response_model=PagedBooksResponse)
def list_books_by_genre(
    slug: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=48),
    catalog_service: CatalogService = Depends(get_catalog_service),
) -> PagedBooksResponse:
    return catalog_service.list_books_by_genre(
        slug=slug,
        page=page,
        page_size=page_size,
    )
