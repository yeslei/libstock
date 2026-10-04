from decimal import Decimal

from app.core.exceptions import CopySalePriceRequiredError
from app.models.domain import DestinationType


def require_commercial_price(destination: DestinationType, price: Decimal | None) -> None:
    """Exemplar comercial exige preço de venda maior que zero, na inclusão e na edição (Issue #175).

    Mesmo código e mensagem (`copy_sale_price_required`, 422) nos dois fluxos; o banco mantém
    `sale_price >= 0` apenas como última barreira estrutural.
    """
    if destination == DestinationType.COMMERCIAL and (price is None or Decimal(price) <= 0):
        raise CopySalePriceRequiredError()
