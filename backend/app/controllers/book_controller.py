from fastapi import APIRouter, Depends, status

from app.dependencies.authentication import require_roles
from app.dependencies.services import get_book_service
from app.models.user import User
from app.schemas.book_schema import BookCreate, BookResponse
from app.services.book_service import BookService

router = APIRouter(prefix="/api/v1/books", tags=["Books"])

@router.post("/", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_book(
    book_data: BookCreate,
    current_user: User = Depends(
        require_roles("STOCK_KEEPER", "MANAGER", "ADMINISTRATOR")
    ),
    service: BookService = Depends(get_book_service),
) -> BookResponse:
    return await service.create_book(book_data, employee_id=current_user.id)
