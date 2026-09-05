from pydantic import BaseModel, Field
from typing import Literal

class CopyCreate(BaseModel):
    barcode: str = Field(..., description="Identificador único para leitura no caixa")
    destinationTag: Literal["Didático", "Comercial"] = Field(
        ..., 
        description="Tag obrigatória que define a destinação do exemplar"
    )
    book_id: int = Field(..., description="Referência para a obra à qual o exemplar pertence")

class CopyResponse(CopyCreate):
    id: int
    status: str = Field(default="Available", description="Estado inicial do exemplar")

    class Config:
        orm_mode = True