from fastapi import APIRouter, Depends

from app.dependencies.services import get_book_service
from app.schemas.book_schema import BookResponse, BookSearchParams
from app.services.book_service import BookService


router = APIRouter(prefix="/api/v1/books", tags=["Obras"])


@router.get("/", response_model=list[BookResponse])
def search_books(
    params: BookSearchParams = Depends(),
    book_service: BookService = Depends(get_book_service),
) -> list[BookResponse]:
    return book_service.search_books(params.title)
