from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.dependencies.services import get_catalog_service
from app.schemas.catalog_schema import (
    CatalogBookResponse,
    CatalogSearchParams,
    GenreResponse,
    PagedBooksResponse,
)
from app.services.catalog_service import CatalogService


# Rotas públicas: a vitrine é navegável sem sessão. O login só é exigido nas
# ações transacionais, que vivem fora deste controller.
router = APIRouter(prefix="/api/v1/catalog", tags=["Catálogo"])


def get_catalog_search_params(
    title: Annotated[str | None, Query()] = None,
    author: Annotated[str | None, Query()] = None,
) -> CatalogSearchParams:
    try:
        return CatalogSearchParams(title=title, author=author)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


@router.get("/featured-books", response_model=list[CatalogBookResponse])
def list_featured_books(
    catalog_service: CatalogService = Depends(get_catalog_service),
) -> list[CatalogBookResponse]:
    return catalog_service.list_featured_books()


@router.get("/books", response_model=list[CatalogBookResponse])
def search_books(
    params: CatalogSearchParams = Depends(get_catalog_search_params),
    catalog_service: CatalogService = Depends(get_catalog_service),
) -> list[CatalogBookResponse]:
    return catalog_service.search_books(
        title=params.title,
        author=params.author,
    )


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