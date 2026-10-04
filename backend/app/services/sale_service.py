from datetime import datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.business_dates import BUSINESS_ZONE as ZONE
from app.core.exceptions import (
    ApplicationError, BookInactiveError, ClientInactiveError, ClientNotFoundError, CopyInactiveError,
    CopyNotAvailableError, CopyNotFoundError, CopyNotForSaleError, CopyReservedError, CopyWithoutPriceError,
    DuplicateSaleItemError, SaleConflictError, SalePersistenceError,
)
from app.models.domain import CopyStatus, DestinationType
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
        # Issue #175: o mesmo exemplar duas vezes nos itens é pedido inválido (422), nunca erro do banco (500).
        item_ids = [item.copy_id for item in sale_data.items]
        if len(set(item_ids)) != len(item_ids):
            raise DuplicateSaleItemError()

        try:
            # Penalidade não bloqueia a venda (pagamento no balcão); só cliente inexistente ou inativo.
            active = self.repository.client_active_state(sale_data.client_id)

            if active is None:
                raise ClientNotFoundError()

            if not active:
                raise ClientInactiveError()

            copy_ids = [item.copy_id for item in sale_data.items]

            books = self.repository.lock_books_for_copies(copy_ids)
            # Reservas vencidas liberam o exemplar: efetiva a expiração antes de travar os exemplares.
            self.repository.expire_due_reservations(books.keys(), datetime.now(ZONE))
            copies = self.repository.find_copies_for_sale(copy_ids)
            reserved = self.repository.reserved_copy_ids(copy_ids)

            copies_by_id = {copy.id: copy for copy in copies}

            if len(copies_by_id) != len(set(copy_ids)):
                raise CopyNotFoundError("Um ou mais exemplares não foram encontrados.")

            for copy in copies:
                if not copy.is_active:
                    raise CopyInactiveError("Um ou mais exemplares estão inativos.")

                book = books.get(copy.book_id)
                if book is None or not book.is_active:
                    raise BookInactiveError()

                if copy.status != CopyStatus.AVAILABLE:
                    raise CopyNotAvailableError("Um ou mais exemplares não estão disponíveis para venda.")

                if copy.id in reserved:
                    raise CopyReservedError()

                if copy.destination == DestinationType.DIDACTIC:
                    raise CopyNotForSaleError()

            # O preço é sempre o cadastrado no exemplar (banco); o valor enviado é ignorado.
            priced_items = []
            for item in sale_data.items:
                price = copies_by_id[item.copy_id].sale_price
                if price is None:
                    raise CopyWithoutPriceError()
                priced_items.append((item.copy_id, price))

            total_amount = sum(
                (price for _, price in priced_items),
                Decimal("0.00"),
            )

            sale = self.repository.create_sale(
                client_id=sale_data.client_id,
                employee_id=employee_id,
                total_amount=total_amount,
            )

            sale_items = self.repository.create_sale_items(
                sale_id=sale.id,
                items=priced_items,
            )

            # Venda direta é paga no balcão: confirma no ato. O gatilho do banco
            # (mesmo mecanismo do confirm-sale V2) marca o exemplar como SOLD,
            # recalcula o total e registra o funcionário na auditoria.
            self.repository.confirm_sale(sale)

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

        except IntegrityError as exc:
            self.db.rollback()
            raise SaleConflictError() from exc

        except SQLAlchemyError as exc:
            self.db.rollback()
            raise SalePersistenceError() from exc