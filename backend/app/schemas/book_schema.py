from pydantic import BaseModel, ConfigDict, Field

class BookCreate(BaseModel):
    isbn: str = Field(min_length=10, max_length=17)
    title: str = Field(min_length=1, max_length=255)
    author: str = Field(min_length=1, max_length=255)
    genre: str | None = Field(default=None, max_length=100)
    publication_year: int | None = Field(default=None, ge=1000, le=2100)
    publisher: str | None = Field(default=None, max_length=150)
    edition: str | None = Field(default=None, max_length=50)
    cover_url: str | None = None


class BookLookupResponse(BaseModel):
    isbn: str
    title: str
    author: str
    genre: str | None = None
    publication_year: int | None = None
    publisher: str | None = None
    edition: str | None = None
    cover_url: str | None = None

class BookResponse(BookCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)