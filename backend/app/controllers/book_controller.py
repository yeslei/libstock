from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.dependencies.services import get_db
from app.services.book_service import BookService
from app.schemas.book_schema import BookCreate, BookResponse

router = APIRouter(prefix="/api/v1/books", tags=["Books"])

@router.post("/", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_book(book_data: BookCreate, db: Session = Depends(get_db)):
    service = BookService(db)
    return await service.create_book(book_data)