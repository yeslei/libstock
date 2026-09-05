import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.repositories.book_repository import BookRepository
from app.schemas.book_schema import BookCreate, BookLookupResponse

class BookService:
    def __init__(self, db: Session):
        self.repository = BookRepository(db)

    async def lookup_google_books(self, isbn: str) -> BookLookupResponse:
        url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Não foi possível consultar o Google Books.") from exc

        if data.get("totalItems", 0) == 0 or not data.get("items"):
            raise HTTPException(status_code=404, detail="ISBN não encontrado no Google Books.")

        volume_info = data["items"][0].get("volumeInfo", {})
        published_date = volume_info.get("publishedDate", "")
        publication_year = int(published_date[:4]) if published_date[:4].isdigit() else None
        image_links = volume_info.get("imageLinks", {})

        return BookLookupResponse(
            isbn=isbn,
            title=volume_info.get("title", ""),
            author=", ".join(volume_info.get("authors", [])),
            genre=(volume_info.get("categories") or [None])[0],
            publication_year=publication_year,
            publisher=volume_info.get("publisher"),
            edition=volume_info.get("edition"),
            cover_url=image_links.get("thumbnail"),
        )

    def create_book(self, book_data: BookCreate):
        return self.repository.create_book(book_data)