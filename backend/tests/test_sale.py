from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.controllers.sale_controller import create_sale
from app.models.domain import CopyStatus, SaleStatus
from app.schemas.sale_schema import SaleCreate
from app.services.sale_service import SaleService


def _sale_data() -> SaleCreate:
    return SaleCreate(
        client_id=42,
        items=[
            {"copy_id": 15, "unit_price": Decimal("39.90")},
            {"copy_id": 16, "unit_price": Decimal("29.90")},
        ],
    )


def _copy(
    copy_id: int = 15,
    *,
    status_: CopyStatus = CopyStatus.AVAILABLE,
    is_active: bool = True,
):
    return SimpleNamespace(
        id=copy_id,
        status=status_,
        is_active=is_active,
    )


def _sale_entity(
    sale_data: SaleCreate,
    *,
    employee_id: int = 7,
    sale_id: int = 100,
):
    total = sum(
        (item.unit_price for item in sale_data.items),
        Decimal("0.00"),
    )

    items = [
        SimpleNamespace(
            id=index,
            sale_id=sale_id,
            copy_id=item.copy_id,
            unit_price=item.unit_price,
        )
        for index, item in enumerate(sale_data.items, start=1)
    ]

    return SimpleNamespace(
        id=sale_id,
        client_id=sale_data.client_id,
        employee_id=employee_id,
        sale_date=datetime(2026, 10, 2, 14, 0, tzinfo=timezone.utc),
        total_amount=total,
        status=SaleStatus.PENDING,
        items=items,
    )


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.refreshed = []

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, obj):
        self.refreshed.append(obj)


class FakeSaleService:
    def __init__(self) -> None:
        self.created: list[tuple[SaleCreate, int]] = []

    def create_sale(self, sale_data: SaleCreate, *, employee_id: int):
        self.created.append((sale_data, employee_id))
        return _sale_entity(sale_data, employee_id=employee_id)


def _service(
    repository: MagicMock,
    db: FakeSession,
) -> SaleService:
    return SaleService(
        repository=repository,
        db=db,
    )


def test_service_registra_venda_com_sucesso_e_calcula_total():
    repository = MagicMock()
    db = FakeSession()
    sale_data = _sale_data()

    repository.find_client.return_value = SimpleNamespace(id=42)
    repository.find_copies_for_sale.return_value = [
        _copy(15),
        _copy(16),
    ]

    sale = _sale_entity(sale_data)
    repository.create_sale.return_value = sale

    def create_items(*, sale_id, items):
        return [
            SimpleNamespace(
                id=index,
                sale_id=sale_id,
                copy_id=item.copy_id,
                unit_price=item.unit_price,
            )
            for index, item in enumerate(items, start=1)
        ]

    repository.create_sale_items.side_effect = create_items

    response = _service(repository, db).create_sale(
        sale_data,
        employee_id=7,
    )

    assert response.id == 100
    assert response.client_id == 42
    assert response.employee_id == 7
    assert response.total_amount == Decimal("69.80")
    assert response.status == SaleStatus.PENDING
    assert len(response.items) == 2

    repository.create_sale.assert_called_once()
    create_kwargs = repository.create_sale.call_args.kwargs
    assert create_kwargs["employee_id"] == 7
    assert create_kwargs["total_amount"] == Decimal("69.80")

    repository.create_sale_items.assert_called_once()
    assert db.commits == 1
    assert db.rollbacks == 0
    assert db.refreshed == [sale]


def test_service_permita_venda_sem_cliente():
    repository = MagicMock()
    db = FakeSession()

    sale_data = SaleCreate(
        client_id=None,
        items=[
            {"copy_id": 15, "unit_price": Decimal("39.90")},
        ],
    )

    repository.find_copies_for_sale.return_value = [_copy(15)]

    sale = _sale_entity(sale_data)
    repository.create_sale.return_value = sale
    def create_items(*, sale_id, items):
        return [
            SimpleNamespace(
                id=1,
                sale_id=sale_id,
                copy_id=item.copy_id,
                unit_price=item.unit_price,
            )
            for item in items
        ]

    repository.create_sale_items.side_effect = create_items

    response = _service(repository, db).create_sale(
        sale_data,
        employee_id=7,
    )

    assert response.client_id is None
    repository.find_client.assert_not_called()
    assert db.commits == 1


def test_service_rejeita_cliente_inexistente():
    repository = MagicMock()
    db = FakeSession()
    repository.find_client.return_value = None

    with pytest.raises(HTTPException) as exc:
        _service(repository, db).create_sale(
            _sale_data(),
            employee_id=7,
        )

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    repository.find_copies_for_sale.assert_not_called()
    repository.create_sale.assert_not_called()
    assert db.commits == 0
    assert db.rollbacks == 1


def test_service_rejeita_exemplar_inexistente():
    repository = MagicMock()
    db = FakeSession()

    repository.find_client.return_value = SimpleNamespace(id=42)
    repository.find_copies_for_sale.return_value = [_copy(15)]

    with pytest.raises(HTTPException) as exc:
        _service(repository, db).create_sale(
            _sale_data(),
            employee_id=7,
        )

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    repository.create_sale.assert_not_called()
    assert db.commits == 0
    assert db.rollbacks == 1


@pytest.mark.parametrize(
    ("copy_status", "is_active", "expected_status"),
    [
        (CopyStatus.BORROWED, True, status.HTTP_409_CONFLICT),
        (CopyStatus.SOLD, True, status.HTTP_409_CONFLICT),
        (CopyStatus.RESERVED, True, status.HTTP_409_CONFLICT),
        (CopyStatus.INACTIVE, False, status.HTTP_404_NOT_FOUND),
        (CopyStatus.AVAILABLE, False, status.HTTP_404_NOT_FOUND),
    ],
)
def test_service_rejeita_exemplar_indisponivel_ou_inativo(
    copy_status: CopyStatus,
    is_active: bool,
    expected_status: int,
):
    repository = MagicMock()
    db = FakeSession()

    repository.find_client.return_value = SimpleNamespace(id=42)
    repository.find_copies_for_sale.return_value = [
        _copy(
            15,
            status_=copy_status,
            is_active=is_active,
        ),
        _copy(16),
    ]

    with pytest.raises(HTTPException) as exc:
        _service(repository, db).create_sale(
            _sale_data(),
            employee_id=7,
        )

    assert exc.value.status_code == expected_status
    repository.create_sale.assert_not_called()
    repository.create_sale_items.assert_not_called()
    assert db.commits == 0
    assert db.rollbacks == 1


def test_service_trata_erro_de_integridade_com_rollback():
    repository = MagicMock()
    db = FakeSession()

    repository.find_client.return_value = SimpleNamespace(id=42)
    repository.find_copies_for_sale.return_value = [
        _copy(15),
        _copy(16),
    ]
    repository.create_sale.side_effect = IntegrityError(
        "insert",
        {},
        Exception("integrity error"),
    )

    with pytest.raises(HTTPException) as exc:
        _service(repository, db).create_sale(
            _sale_data(),
            employee_id=7,
        )

    assert exc.value.status_code == status.HTTP_409_CONFLICT
    assert db.rollbacks == 1
    assert db.commits == 0


def test_service_trata_falha_de_banco_com_rollback():
    class DatabaseError(SQLAlchemyError):
        pass

    repository = MagicMock()
    db = FakeSession()

    repository.find_client.return_value = SimpleNamespace(id=42)
    repository.find_copies_for_sale.return_value = [
        _copy(15),
        _copy(16),
    ]
    repository.create_sale.side_effect = DatabaseError(
        "database error"
    )

    with pytest.raises(HTTPException) as exc:
        _service(repository, db).create_sale(
            _sale_data(),
            employee_id=7,
        )

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert db.rollbacks == 1
    assert db.commits == 0


def test_controller_passa_usuario_autenticado_para_o_service():
    fake = FakeSaleService()
    sale_data = _sale_data()

    response = create_sale(
        sale_data=sale_data,
        current_user=SimpleNamespace(id=7),
        sale_service=fake,
    )

    created_data, employee_id = fake.created[0]

    assert created_data == sale_data
    assert employee_id == 7
    assert response.id == 100
    assert response.total_amount == Decimal("69.80")
    assert response.status == SaleStatus.PENDING


def test_schema_rejeita_venda_sem_itens():
    with pytest.raises(ValidationError):
        SaleCreate(
            client_id=42,
            items=[],
        )


def test_schema_rejeita_id_de_exemplar_invalido():
    with pytest.raises(ValidationError):
        SaleCreate(
            client_id=42,
            items=[
                {
                    "copy_id": 0,
                    "unit_price": Decimal("39.90"),
                }
            ],
        )


def test_schema_rejeita_preco_negativo():
    with pytest.raises(ValidationError):
        SaleCreate(
            client_id=42,
            items=[
                {
                    "copy_id": 15,
                    "unit_price": Decimal("-1.00"),
                }
            ],
        )
