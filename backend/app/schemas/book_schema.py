from pydantic import BaseModel, ConfigDict, Field, field_validator


class BookSearchParams(BaseModel):
    title: str = Field(min_length=1, pattern=r".*\S.*")

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("O título da busca não pode estar vazio.")
        return normalized


class BookResponse(BaseModel):
    id: int
    title: str
    author: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
