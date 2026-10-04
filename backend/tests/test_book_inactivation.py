"""Inativação de obra bloqueada por operações em andamento (Issue #135): regras do service e contrato HTTP."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import BookHasActiveOperationsError
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_book_service
from app.main import app
from app.schemas.book_schema import BookUpdate
from app.services.book_service import BookService

NONE = {"open_loans": 0, "pending_loan_requests": 0, "purchase_reservations": 0}


class Repository:
    def __init__(self, *, counts=None, active=True):
        self.db = MagicMock()
        self.book = SimpleNamespace(
            id=1, isbn=None, title="Obra", author="Autora", genre=None, cover_url=None,
            is_active=active, initial_copy=None, copies=[],
        )
        self.counts = counts or dict(NONE)
        self.calls: list[str] = []

    def employee_exists(self, _id):
        return True

    def get_with_copies(self, _id):
        return self.book

    def find_by_isbn_except(self, *_args):
        return None

    def lock_book_for_inactivation(self, book_id, now):
        self.calls.append(f"lock({book_id})")

    def active_operation_counts(self, book_id):
        self.calls.append(f"counts({book_id})")
        return self.counts

    def active_operation_links(self, _book_id, *, include_clients=False):
        return [{"type": "open_loan", "copy_barcode": "00102", "client_name": "Maria"}]

    def update_book(self, book, changes):
        self.calls.append("update")
        for key, value in changes.model_dump(exclude_unset=True).items():
            setattr(book, key, value)
        return book


def service(repository):
    return BookService(db=repository.db, repository=repository)


@pytest.mark.parametrize("key", ["open_loans", "pending_loan_requests", "purchase_reservations"])
def test_inativacao_bloqueada_por_cada_tipo_de_operacao(key):
    repository = Repository(counts={**NONE, key: 2})
    with pytest.raises(BookHasActiveOperationsError) as error:
        service(repository).update_book(1, BookUpdate(is_active=False), employee_id=9)
    assert (error.value.status_code, error.value.code) == (409, "book_has_active_operations")
    assert error.value.details["counts"][key] == 2
    assert error.value.details["links"][0]["copy_barcode"] == "00102"
    assert repository.book.is_active is True
    assert "update" not in repository.calls
    repository.db.rollback.assert_called_once()
    repository.db.commit.assert_not_called()


def test_inativacao_sem_operacoes_trava_o_livro_antes_de_contar_e_confirma():
    repository = Repository()
    result = service(repository).update_book(1, BookUpdate(is_active=False), employee_id=9)
    assert result.is_active is False
    assert repository.calls == ["lock(1)", "counts(1)", "update"]
    repository.db.commit.assert_called_once()


def test_outras_alteracoes_e_obra_ja_inativa_nao_consultam_operacoes():
    busy = Repository(counts={**NONE, "open_loans": 1})
    service(busy).update_book(1, BookUpdate(title="Novo título"), employee_id=9)
    service(busy).update_book(1, BookUpdate(is_active=True), employee_id=9)
    inactive = Repository(counts={**NONE, "open_loans": 1}, active=False)
    service(inactive).update_book(1, BookUpdate(is_active=False), employee_id=9)
    assert not any(call.startswith("counts") for call in busy.calls + inactive.calls)


class Stub:
    def update_book(self, _book_id, _changes, *, employee_id, can_view_clients):
        self.seen = can_view_clients
        raise BookHasActiveOperationsError(
            {"open_loans": 1, "pending_loan_requests": 0, "purchase_reservations": 0},
            [{"type": "open_loan", "copy_barcode": "00102", "client_name": "Maria"}],
        )


def test_http_409_expoe_codigo_estavel_contagens_e_vinculos():
    app.dependency_overrides[get_book_service] = Stub
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role_codes=["ADMINISTRATOR"])
    try:
        response = TestClient(app).patch("/api/v1/books/1", json={"is_active": False})
    finally:
        app.dependency_overrides.clear()
    body = response.json()
    assert (response.status_code, body["code"]) == (409, "book_has_active_operations")
    assert body["details"]["counts"] == {"open_loans": 1, "pending_loan_requests": 0, "purchase_reservations": 0}
    assert body["details"]["links"][0]["client_name"] == "Maria"


class Recorder:
    seen: list[bool] = []

    def update_book(self, _book_id, _changes, *, employee_id, can_view_clients):
        Recorder.seen.append(can_view_clients)
        return {"id": 1, "isbn": None, "title": "Obra", "author": "A", "genre": None, "cover_url": None,
                "is_active": False, "initial_copy": None, "copies": []}


@pytest.mark.parametrize("roles,expected", [
    (["ADMINISTRATOR"], True), (["SELLER"], True), (["STOCK_KEEPER"], False), (["MANAGER"], False),
])
def test_dados_de_cliente_so_para_administrador_e_vendedor(roles, expected):
    Recorder.seen = []
    app.dependency_overrides[get_book_service] = Recorder
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role_codes=roles)
    try:
        response = TestClient(app).patch("/api/v1/books/1", json={"is_active": False})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert Recorder.seen == [expected]


def test_service_repassa_a_permissao_ao_repository():
    repository = Repository(counts={**NONE, "open_loans": 1})
    seen = []
    repository.active_operation_links = lambda _id, *, include_clients=False: seen.append(include_clients) or []
    for allowed in (True, False):
        with pytest.raises(BookHasActiveOperationsError):
            service(repository).update_book(1, BookUpdate(is_active=False), employee_id=9, can_view_clients=allowed)
    assert seen == [True, False]
