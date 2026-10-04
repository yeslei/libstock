"""Exclusão de exemplar (Issue #135): contrato HTTP, regras do service e falhas de persistência."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, OperationalError

from app.controllers.copy_controller import get_copy_service
from app.core.exceptions import (
    ApplicationError,
    CopyDeletionBlockedError,
    CopyNotFoundError,
    EmployeeRecordRequiredError,
    UserInactiveError,
)
from app.dependencies.authentication import get_current_user
from app.main import app
from app.models.domain import CopyStatus
from app.schemas.copy_schema import CopyDeleteResponse
from app.services.copy_service import CopyService

NO_HISTORY = {"loans": 0, "sales": 0, "purchase_reservations": 0, "requests": 0}


class FakeRepository:
    def __init__(
        self,
        *,
        copy=None,
        book=None,
        employee=True,
        history=None,
        other_active=True,
        delete_error: Exception | None = None,
    ):
        self.copy = copy
        self.book = book if book is not None else SimpleNamespace(id=1, is_active=True)
        self.employee = employee
        self.history = history or dict(NO_HISTORY)
        self.other_active = other_active
        self.delete_error = delete_error
        self.calls: list[str] = []

    def is_active_employee(self, user_id):
        self.calls.append(f"is_active_employee({user_id})")
        return self.employee

    def set_audit_actor(self, employee_id):
        self.calls.append(f"set_audit_actor({employee_id})")

    def find_copy(self, copy_id):
        self.calls.append(f"find_copy({copy_id})")
        return self.copy

    def lock_book(self, book_id):
        self.calls.append(f"lock_book({book_id})")
        return self.book

    def lock_copy(self, copy_id):
        self.calls.append(f"lock_copy({copy_id})")
        return self.copy

    def history_counts(self, copy_id):
        return self.history

    def has_other_active_copy(self, book_id, copy_id):
        return self.other_active

    def delete_copy(self, copy):
        self.calls.append("delete_copy")
        if self.delete_error is not None:
            raise self.delete_error


class FakeSession:
    def __init__(self, commit_error: Exception | None = None):
        self.commits = 0
        self.rollbacks = 0
        self.commit_error = commit_error

    def commit(self):
        if self.commit_error is not None:
            raise self.commit_error
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def a_copy(**over):
    values = dict(id=9, book_id=1, barcode="EX-9", status=CopyStatus.AVAILABLE, is_active=True)
    values.update(over)
    return SimpleNamespace(**values)


def delete(repository, session=None, copy_id=9, actor_id=7):
    session = session or FakeSession()
    return CopyService(repository, session).delete_copy(copy_id=copy_id, actor_id=actor_id), session


def blocked(repository, session=None):
    with pytest.raises(CopyDeletionBlockedError) as error:
        delete(repository, session)
    return error.value


def test_exclusao_bem_sucedida_trava_livro_antes_do_exemplar_e_registra_o_ator():
    repository = FakeRepository(copy=a_copy())
    response, session = delete(repository)
    assert response == CopyDeleteResponse(id=9, book_id=1, barcode="EX-9")
    assert (session.commits, session.rollbacks) == (1, 0)
    assert repository.calls == [
        "is_active_employee(7)", "set_audit_actor(7)", "find_copy(9)",
        "lock_book(1)", "lock_copy(9)", "delete_copy",
    ]


def test_exemplar_inexistente_ou_removido_durante_a_espera_do_lock_retorna_404():
    with pytest.raises(CopyNotFoundError) as missing:
        delete(FakeRepository(copy=None))
    assert (missing.value.status_code, missing.value.code) == (404, "copy_not_found")

    class RemovedWhileWaiting(FakeRepository):
        def lock_copy(self, copy_id):
            return None

    with pytest.raises(CopyNotFoundError):
        delete(RemovedWhileWaiting(copy=a_copy()))


def test_funcionario_inativo_ou_sem_cadastro_nao_exclui_nem_audita():
    repository = FakeRepository(copy=a_copy(), employee=False)
    session = FakeSession()
    with pytest.raises(EmployeeRecordRequiredError) as error:
        delete(repository, session)
    assert error.value.status_code == 403
    assert repository.calls == ["is_active_employee(7)"]
    assert session.rollbacks == 1


@pytest.mark.parametrize("status", [CopyStatus.BORROWED, CopyStatus.SOLD, CopyStatus.RESERVED, CopyStatus.INACTIVE])
def test_bloqueia_exemplar_que_nao_esta_disponivel(status):
    repository = FakeRepository(copy=a_copy(status=status))
    error = blocked(repository)
    assert (error.status_code, error.code) == (409, "copy_not_available")
    assert [reason["code"] for reason in error.details["reasons"]] == ["copy_not_available"]
    assert "delete_copy" not in repository.calls


@pytest.mark.parametrize("key", ["loans", "sales", "purchase_reservations", "requests"])
def test_bloqueia_exemplar_com_historico(key):
    repository = FakeRepository(copy=a_copy(), history={**NO_HISTORY, key: 1})
    error = blocked(repository)
    assert (error.status_code, error.code) == (409, "copy_has_history")
    assert error.details["history"][key] == 1
    assert "delete_copy" not in repository.calls


def test_bloqueia_ultimo_exemplar_ativo_de_obra_ativa():
    error = blocked(FakeRepository(copy=a_copy(), other_active=False))
    assert (error.status_code, error.code) == (409, "last_active_copy")


def test_ultimo_exemplar_de_obra_inativa_ou_exemplar_inativo_nao_e_bloqueado_por_essa_regra():
    delete(FakeRepository(copy=a_copy(), other_active=False, book=SimpleNamespace(id=1, is_active=False)))
    delete(FakeRepository(copy=a_copy(is_active=False), other_active=False))


def test_acumula_todos_os_motivos_e_usa_o_primeiro_como_codigo():
    repository = FakeRepository(
        copy=a_copy(status=CopyStatus.BORROWED), history={**NO_HISTORY, "loans": 2}, other_active=False
    )
    error = blocked(repository)
    assert error.code == "copy_not_available"
    assert [reason["code"] for reason in error.details["reasons"]] == [
        "copy_not_available", "copy_has_history", "last_active_copy",
    ]
    assert error.message.startswith("Exclusão bloqueada: ")


def test_bloqueio_faz_rollback_sem_commit():
    session = FakeSession()
    blocked(FakeRepository(copy=a_copy(status=CopyStatus.SOLD)), session)
    assert (session.commits, session.rollbacks) == (0, 1)


class Driver(Exception):
    def __init__(self, message, sqlstate=None):
        super().__init__(message)
        self.sqlstate = sqlstate


def test_fk_inesperada_vira_bloqueio_nunca_500():
    failure = IntegrityError("DELETE", {}, Driver("violates foreign key constraint", "23503"))
    session = FakeSession()
    with pytest.raises(CopyDeletionBlockedError) as error:
        delete(FakeRepository(copy=a_copy(), delete_error=failure), session)
    assert (error.value.status_code, error.value.code) == (409, "copy_has_history")
    assert (session.commits, session.rollbacks) == (0, 1)


def test_gatilho_do_ultimo_exemplar_no_commit_vira_bloqueio():
    failure = OperationalError("COMMIT", {}, Driver("An active book requires at least one active copy"))
    session = FakeSession(commit_error=failure)
    with pytest.raises(CopyDeletionBlockedError) as error:
        delete(FakeRepository(copy=a_copy()), session)
    assert error.value.code == "last_active_copy"
    assert session.rollbacks == 1


def test_falha_de_persistencia_desconhecida_retorna_500_com_codigo_estavel_e_rollback():
    failure = OperationalError("DELETE", {}, Driver("connection lost"))
    session = FakeSession()
    with pytest.raises(ApplicationError) as error:
        delete(FakeRepository(copy=a_copy(), delete_error=failure), session)
    assert (error.value.status_code, error.value.code) == (500, "copy_delete_persistence_error")
    assert (session.commits, session.rollbacks) == (0, 1)


class StubService:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[tuple[int, int]] = []

    def delete_copy(self, *, copy_id, actor_id):
        self.calls.append((copy_id, actor_id))
        if self.error is not None:
            raise self.error
        return CopyDeleteResponse(id=copy_id, book_id=1, barcode="EX-9")


@pytest.fixture
def http():
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def as_user(roles, user_id=7):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id, role_codes=roles)


def test_http_sem_token_retorna_401(http):
    app.dependency_overrides[get_copy_service] = lambda: StubService()
    response = http.delete("/api/v1/copies/9")
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


@pytest.mark.parametrize("role", ["SELLER", "MANAGER", "USER"])
def test_http_papeis_sem_permissao_retornam_403_sem_chamar_o_service(http, role):
    service = StubService()
    app.dependency_overrides[get_copy_service] = lambda: service
    as_user([role])
    response = http.delete("/api/v1/copies/9")
    assert (response.status_code, response.json()["code"]) == (403, "permission_denied")
    assert service.calls == []


def test_http_usuario_inativo_retorna_403(http):
    def inactive():
        raise UserInactiveError()

    app.dependency_overrides[get_copy_service] = lambda: StubService()
    app.dependency_overrides[get_current_user] = inactive
    response = http.delete("/api/v1/copies/9")
    assert (response.status_code, response.json()["code"]) == (403, "user_inactive")


@pytest.mark.parametrize("role", ["STOCK_KEEPER", "ADMINISTRATOR"])
def test_http_papeis_autorizados_excluem_com_200(http, role):
    service = StubService()
    app.dependency_overrides[get_copy_service] = lambda: service
    as_user([role], user_id=4)
    response = http.delete("/api/v1/copies/9")
    assert response.status_code == 200
    assert response.json() == {"id": 9, "book_id": 1, "barcode": "EX-9", "deleted": True}
    assert service.calls == [(9, 4)]


def test_http_404_e_409_expoem_codigo_estavel_e_motivos(http):
    as_user(["ADMINISTRATOR"])
    app.dependency_overrides[get_copy_service] = lambda: StubService(CopyNotFoundError())
    missing = http.delete("/api/v1/copies/9")
    assert (missing.status_code, missing.json()["code"]) == (404, "copy_not_found")

    reasons = [{"code": "copy_has_history", "message": "histórico"}]
    app.dependency_overrides[get_copy_service] = lambda: StubService(
        CopyDeletionBlockedError(reasons, {**NO_HISTORY, "loans": 1})
    )
    conflict = http.delete("/api/v1/copies/9")
    body = conflict.json()
    assert (conflict.status_code, body["code"]) == (409, "copy_has_history")
    assert body["details"]["reasons"] == reasons
    assert body["details"]["history"]["loans"] == 1


def test_http_id_invalido_retorna_422(http):
    as_user(["ADMINISTRATOR"])
    app.dependency_overrides[get_copy_service] = lambda: StubService()
    assert http.delete("/api/v1/copies/abc").status_code == 422
