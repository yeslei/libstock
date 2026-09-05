from fastapi import HTTPException
from app.repositories.copy_repository import CopyRepository
from app.schemas.copy_schema import CopyCreate

class CopyService:
    def __init__(self, repository: CopyRepository):
        self.repository = repository

    def create_new_copy(self, copy_data: CopyCreate):
        try:
            return self.repository.create_copy(copy_data=copy_data)
        except Exception as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Erro ao cadastrar exemplar. Verifique os dados. Detalhes: {str(e)}"
            )