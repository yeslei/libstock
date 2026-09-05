from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.dependencies.services import get_db
from app.services.book_service import BookService
from app.schemas.book_schema import BookCreate, BookLookupResponse, BookResponse

router = APIRouter(prefix="/api/v1/books", tags=["Books"])

@router.get("/lookup", response_model=BookLookupResponse)
async def lookup_book(
    isbn: str = Query(min_length=10, max_length=17),
    db: Session = Depends(get_db),
):
    service = BookService(db)
    return await service.lookup_google_books(isbn)

@router.post("/", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
def create_book(book_data: BookCreate, db: Session = Depends(get_db)):
    service = BookService(db)
    return service.create_book(book_data)