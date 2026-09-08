from fastapi import APIRouter, Depends, status

from app.dependencies.authentication import require_roles
from app.dependencies.services import get_book_service
from app.models.user import User
from app.schemas.book_schema import (
    BookCreate,
    BookDetailResponse,
    BookResponse,
    BookSearchParams,
    BookUpdate,
)
from app.services.book_service import BookService

router = APIRouter(prefix="/api/v1/books", tags=["Books"])

@router.post("/", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_book(
    book_data: BookCreate,
    current_user: User = Depends(
        require_roles("STOCK_KEEPER", "ADMINISTRATOR")
    ),
    service: BookService = Depends(get_book_service),
) -> BookResponse:
    return await service.create_book(book_data, employee_id=current_user.id)


@router.get("/", response_model=list[BookResponse])
def search_books(
    params: BookSearchParams = Depends(),
    book_service: BookService = Depends(get_book_service),
) -> list[BookResponse]:
    return book_service.search_books(params.title)


@router.get("/{book_id}", response_model=BookDetailResponse)
def get_book(
    book_id: int,
    current_user: User = Depends(require_roles("STOCK_KEEPER", "ADMINISTRATOR")),
    service: BookService = Depends(get_book_service),
) -> BookDetailResponse:
    return service.get_book(book_id)


@router.patch("/{book_id}", response_model=BookDetailResponse)
def update_book(
    book_id: int,
    changes: BookUpdate,
    current_user: User = Depends(require_roles("STOCK_KEEPER", "ADMINISTRATOR")),
    service: BookService = Depends(get_book_service),
) -> BookDetailResponse:
    return service.update_book(book_id, changes, employee_id=current_user.id)
