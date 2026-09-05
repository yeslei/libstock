from typing import Optional
from pydantic import BaseModel, ConfigDict

class BookCreate(BaseModel):
    isbn: str
    title: Optional[str] = None
    author: Optional[str] = None
    genre: Optional[str] = None

class BookResponse(BookCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)