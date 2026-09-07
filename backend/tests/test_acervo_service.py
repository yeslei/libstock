from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import (
    AcervoItemNotFoundError,
    AcervoPersistenceError,
    AuditActorRequiredError,
    DestinationTagNotFoundError,
)
from app.schemas.acervo_schema import ClassifyItemInput
from app.services.acervo_service import AcervoService


class FakeAcervoRepository:
    def __init__(self) -> None:
        self.employee = True
        self.item: SimpleNamespace | None = SimpleNamespace(
            id=1,
            book_id=10,
            barcode="BC-001",
            destination="DIDACTIC",
            status="AVAILABLE",
            destination_tag_id=None,
            destination_tag=None,
        )
        self.tag: SimpleNamespace | None = SimpleNamespace(
            id=3,
            name="Venda",
            slug="venda",
            description="Para venda",
        )
        self.calls: list[str] = []

    def is_employee(self, user_id: int) -> bool:
        self.calls.append(f"is_employee({user_id})")
        return self.employee

    def set_audit_actor(self, employee_id: int) -> None:
        self.calls.append(f"set_audit_actor({employee_id})")

    def find_item_by_id(self, item_id: int):
        self.calls.append(f"find_item_by_id({item_id})")
        return self.item

    def find_tag_by_id(self, tag_id: int):
        self.calls.append(f"find_tag_by_id({tag_id})")
        return self.tag

    def find_tag_by_name_or_slug(self, name_or_slug: str):
        self.calls.append(f"find_tag_by_name_or_slug({name_or_slug})")
        return self.tag

    def list_tags(self):
        self.calls.append("list_tags")
        return [self.tag] if self.tag else []

    def assign_tag(self, item, tag):
        self.calls.append("assign_tag")
        item.destination_tag_id = tag.id
        item.destination_tag = tag
        return item


def _setup_service():
    db = MagicMock()
    repo = FakeAcervoRepository()
    service = AcervoService(db=db, acervo_repository=repo)
    return service, db, repo


def test_classify_item_sucesso_por_tag_id():
    service, db, repo = _setup_service()
    payload = ClassifyItemInput(tag_id=3)

    result = service.classify_item(1, payload, actor_id=99)

    assert result.destination_tag_id == 3
    assert result.destination_tag.name == "Venda"
    assert repo.calls == [
        "is_employee(99)",
        "find_item_by_id(1)",
        "find_tag_by_id(3)",
        "set_audit_actor(99)",
        "assign_tag",
    ]
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(result)


def test_classify_item_sucesso_por_tag_name():
    service, db, repo = _setup_service()
    payload = ClassifyItemInput(tag_name="venda")

    result = service.classify_item(1, payload, actor_id=99)

    assert result.destination_tag_id == 3
    assert "find_tag_by_name_or_slug(venda)" in repo.calls
    db.commit.assert_called_once_with()


def test_classify_item_recusa_ator_sem_funcionario():
    service, db, repo = _setup_service()
    repo.employee = False

    with pytest.raises(AuditActorRequiredError):
        service.classify_item(1, ClassifyItemInput(tag_id=3), actor_id=50)

    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()
    assert "set_audit_actor(50)" not in repo.calls


def test_classify_item_inexistente_lanca_erro_de_dominio():
    service, db, repo = _setup_service()
    repo.item = None

    with pytest.raises(AcervoItemNotFoundError):
        service.classify_item(999, ClassifyItemInput(tag_id=3), actor_id=1)

    db.rollback.assert_called_once_with()


def test_classify_tag_inexistente_lanca_erro_de_dominio():
    service, db, repo = _setup_service()
    repo.tag = None

    with pytest.raises(DestinationTagNotFoundError):
        service.classify_item(1, ClassifyItemInput(tag_id=404), actor_id=1)

    db.rollback.assert_called_once_with()


def test_classify_item_falha_de_persistencia_executa_rollback():
    service, db, repo = _setup_service()
    db.commit.side_effect = SQLAlchemyError("falha no banco")

    with pytest.raises(AcervoPersistenceError):
        service.classify_item(1, ClassifyItemInput(tag_id=3), actor_id=1)

    db.rollback.assert_called_once_with()


def test_get_item_inexistente_lanca_erro_de_dominio():
    service, _db, repo = _setup_service()
    repo.item = None

    with pytest.raises(AcervoItemNotFoundError):
        service.get_item(999)

