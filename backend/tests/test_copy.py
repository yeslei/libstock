from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.controllers.copy_controller import create_copy
from app.core.exceptions import AuditActorRequiredError, PermissionDeniedError
from app.dependencies.authentication import require_roles
from app.models.domain import DestinationType
from app.repositories.copy_repository import CopyRepository
from app.schemas.copy_schema import CopyCreate
from app.services.copy_service import CopyService


class FakeCopyService:
    def __init__(self) -> None:
        self.created: list[tuple[CopyCreate, int]] = []

    def create_new_copy(self, *, copy_data: CopyCreate, actor_id: int):
        self.created.append((copy_data, actor_id))
        return SimpleNamespace(
            id=15,
            book_id=copy_data.book_id,
            barcode=copy_data.barcode,
            destination=copy_data.destination,
            condition=copy_data.condition,
            sale_price=copy_data.sale_price,
            acquired_at=copy_data.acquired_at,
            status="AVAILABLE",
            is_active=True,
        )


class FakeCopyRepository:
    def __init__(self, *, employee: bool = True, copy_error: Exception | None = None):
        self.employee = employee
        self.copy_error = copy_error
        self.calls: list[str] = []

    def is_employee(self, user_id: int) -> bool:
        self.calls.append(f"is_employee({user_id})")
        return self.employee

    def set_audit_actor(self, employee_id: int) -> None:
        self.calls.append(f"set_audit_actor({employee_id})")

    def create_copy(self, copy_data: CopyCreate):
        self.calls.append(f"create_copy({copy_data.barcode})")
        if self.copy_error is not None:
            raise self.copy_error
        return SimpleNamespace(
            id=21,
            book_id=copy_data.book_id,
            barcode=copy_data.barcode,
            destination=copy_data.destination,
            condition=copy_data.condition,
            sale_price=copy_data.sale_price,
            acquired_at=copy_data.acquired_at,
            status="AVAILABLE",
            is_active=True,
        )


class FakeSession:
    def __init__(self, *, book=None):
        self.book = book
        self.commits = 0
        self.rollbacks = 0
        self.refreshed = []

    def get(self, _model, _identifier):
        return self.book

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, obj):
        self.refreshed.append(obj)


def _valid_payload() -> dict[str, object]:
    return {
        "barcode": "EX-000001",
        "destination": "COMMERCIAL",
        "sale_price": "39.90",
        "book_id": 1,
    }


def _copy_data(barcode: str = "EX-000001") -> CopyCreate:
    return CopyCreate(
        book_id=1,
        barcode=barcode,
        destination=DestinationType.COMMERCIAL,
        sale_price=Decimal("39.90"),
    )


def test_controller_passa_usuario_autenticado_para_o_service():
    fake = FakeCopyService()

    response = create_copy(
        copy=CopyCreate.model_validate(_valid_payload()),
        copy_service=fake,
        current_user=SimpleNamespace(id=7),
    )

    copy_data, actor_id = fake.created[0]
    assert copy_data.barcode == "EX-000001"
    assert actor_id == 7
    assert response.id == 15


def test_endpoint_preserva_201_e_contrato_da_resposta():
    fake = FakeCopyService()

    response = create_copy(
        copy=CopyCreate.model_validate(_valid_payload()),
        copy_service=fake,
        current_user=SimpleNamespace(id=7),
    )

    assert status.HTTP_201_CREATED == 201
    assert response.id == 15
    assert response.book_id == 1
    assert response.barcode == "EX-000001"
    assert response.destination == DestinationType.COMMERCIAL
    assert response.sale_price == Decimal("39.90")
    assert response.status == "AVAILABLE"
    assert response.is_active is True


def test_roles_existentes_continuam_protegendo_endpoint():
    dependency = require_roles("SELLER", "STOCK_KEEPER", "MANAGER", "ADMINISTRATOR")

    with pytest.raises(PermissionDeniedError):
        dependency(SimpleNamespace(role_codes=["CLIENT"]))


def test_validacao_de_entrada_continua_rejeitando_destinacao_invalida():
    with pytest.raises(ValueError):
        CopyCreate.model_validate({"barcode": "EX-2", "destination": "INVALID", "book_id": 1})


def test_funcionario_valido_permite_criacao():
    repository = FakeCopyRepository()
    session = FakeSession(book=SimpleNamespace(id=1, is_active=True))

    copy = CopyService(repository, session).create_new_copy(
        copy_data=_copy_data(),
        actor_id=7,
    )

    assert copy.barcode == "EX-000001"
    assert session.commits == 1
    assert session.refreshed == [copy]


def test_funcionario_ausente_ou_invalido_gera_excecao_de_dominio():
    repository = FakeCopyRepository(employee=False)
    session = FakeSession(book=SimpleNamespace(id=1, is_active=True))

    with pytest.raises(AuditActorRequiredError):
        CopyService(repository, session).create_new_copy(
            copy_data=_copy_data(),
            actor_id=99,
        )

    assert "set_audit_actor(99)" not in repository.calls


def test_ator_e_configurado_antes_da_criacao():
    repository = FakeCopyRepository()
    session = FakeSession(book=SimpleNamespace(id=1, is_active=True))

    CopyService(repository, session).create_new_copy(copy_data=_copy_data(), actor_id=7)

    assert repository.calls == [
        "is_employee(7)",
        "set_audit_actor(7)",
        "create_copy(EX-000001)",
    ]


def test_obra_inexistente_continua_retornando_404():
    repository = FakeCopyRepository()
    session = FakeSession(book=None)

    with pytest.raises(HTTPException) as exc:
        CopyService(repository, session).create_new_copy(
            copy_data=_copy_data(),
            actor_id=7,
        )

    assert exc.value.status_code == 404


def test_codigo_de_barras_duplicado_continua_retornando_409():
    repository = FakeCopyRepository(copy_error=IntegrityError("insert", {}, Exception()))
    session = FakeSession(book=SimpleNamespace(id=1, is_active=True))

    with pytest.raises(HTTPException) as exc:
        CopyService(repository, session).create_new_copy(
            copy_data=_copy_data("EX-DUP"),
            actor_id=7,
        )

    assert exc.value.status_code == 409
    assert session.rollbacks == 1


def test_falha_inesperada_executa_rollback_e_retorna_erro_controlado():
    repository = FakeCopyRepository(copy_error=RuntimeError("database exploded"))
    session = FakeSession(book=SimpleNamespace(id=1, is_active=True))

    with pytest.raises(HTTPException) as exc:
        CopyService(repository, session).create_new_copy(
            copy_data=_copy_data(),
            actor_id=7,
        )

    assert session.rollbacks == 1
    assert exc.value.status_code == 500
    assert exc.value.detail == "Não foi possível cadastrar o exemplar."


def test_set_audit_actor_usa_libstock_employee_id_com_escopo_transacional():
    db = Mock()
    repository = CopyRepository(db)

    repository.set_audit_actor(42)

    statement, params = db.execute.call_args.args
    assert "libstock.employee_id" in str(statement)
    assert "true" in str(statement)
    assert params == {"valor": "42"}
