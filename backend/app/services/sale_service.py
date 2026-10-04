from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError, BookInactiveError
from app.models.domain import CopyStatus, DestinationType, SaleStatus
from app.repositories.sale_repository import SaleRepository
from app.schemas.sale_schema import SaleCreate, SaleItemResponse, SaleResponse


class SaleService:
    def __init__(
        self,
        repository: SaleRepository,
        db: Session,
    ) -> None:
        self.repository = repository
        self.db = db

    def create_sale(
        self,
        sale_data: SaleCreate,
        *,
        employee_id: int,
    ) -> SaleResponse:
        try:
            if sale_data.client_id is not None:
                client = self.repository.find_client(sale_data.client_id)

                if client is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Cliente não encontrado.",
                    )

            copy_ids = [item.copy_id for item in sale_data.items]

            books = self.repository.lock_books_for_copies(copy_ids)
            copies = self.repository.find_copies_for_sale(copy_ids)

            copies_by_id = {copy.id: copy for copy in copies}

            if len(copies_by_id) != len(set(copy_ids)):
                raise HTTPException(
                    status_code=404,
                    detail="Um ou mais exemplares não foram encontrados.",
                )

            for copy in copies:
                if not copy.is_active:
                    raise HTTPException(
                        status_code=404,
                        detail="Um ou mais exemplares estão inativos.",
                    )

                book = books.get(copy.book_id)
                if book is None or not book.is_active:
                    raise BookInactiveError()

                if copy.status != CopyStatus.AVAILABLE:
                    raise HTTPException(
                        status_code=409,
                        detail="Um ou mais exemplares não estão disponíveis para venda.",
                    )

                if copy.destination == DestinationType.DIDACTIC:
                    raise HTTPException(
                        status_code=409,
                        detail="Exemplares didáticos não podem ser vendidos.",
                    )

            total_amount = sum(
                (item.unit_price for item in sale_data.items),
                Decimal("0.00"),
            )

            sale = self.repository.create_sale(
                client_id=sale_data.client_id,
                employee_id=employee_id,
                total_amount=total_amount,
            )

            sale_items = self.repository.create_sale_items(
                sale_id=sale.id,
                items=sale_data.items,
            )

            self.db.commit()
            self.db.refresh(sale)

            return SaleResponse(
                id=sale.id,
                client_id=sale.client_id,
                employee_id=sale.employee_id,
                sale_date=sale.sale_date,
                total_amount=sale.total_amount,
                status=sale.status,
                items=[
                    SaleItemResponse.model_validate(item)
                    for item in sale_items
                ],
            )

        except ApplicationError:
            self.db.rollback()
            raise

        except HTTPException:
            self.db.rollback()
            raise

        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Não foi possível registrar a venda.",
            ) from exc

        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Não foi possível registrar a venda.",
            ) from exc