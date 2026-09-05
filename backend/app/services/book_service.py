import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.repositories.book_repository import BookRepository
from app.schemas.book_schema import BookCreate

class BookService:
    def __init__(self, db: Session):
        self.repository = BookRepository(db)

    async def fetch_google_books_data(self, isbn: str) -> dict:
        url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
            
            if data.get("totalItems", 0) == 0:
                raise HTTPException(status_code=404, detail="ISBN não encontrado na base externa do Google Books.")
            
            volume_info = data["items"][0]["volumeInfo"]
            return {
                "title": volume_info.get("title", "Título Desconhecido"),
                "author": ", ".join(volume_info.get("authors", ["Autor Desconhecido"])),
                "genre": volume_info.get("categories", ["Geral"])[0]
            }

    async def create_book(self, book_data: BookCreate):
        # Se o usuário não informou título ou autor, busca automaticamente na API do Google Books
        if not book_data.title or not book_data.author:
            external_data = await self.fetch_google_books_data(book_data.isbn)
            book_data.title = book_data.title or external_data["title"]
            book_data.author = book_data.author or external_data["author"]
            book_data.genre = book_data.genre or external_data["genre"]

        return self.repository.create_book(book_data)