"""Testes isolados do cadastro de obras.

Controller, service e repository usam dublês locais: nenhum teste desta unidade
abre o banco configurado para desenvolvimento ou consulta o Google Books real.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.exceptions import (
    BookPersistenceError,
    DuplicateIsbnError,
    EmployeeRecordRequiredError,
    GoogleBooksInvalidResponseError,
    GoogleBooksNotFoundError,
    GoogleBooksUnavailableError,
)
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_book_service
from app.main import app
from app.repositories.book_repository import BookRepository
from app.schemas.book_schema import BookCreate
from app.services.book_service import BookService

client = TestClient(app)


class FakeBookService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[BookCreate, int]] = []

    async def create_book(self, book_data: BookCreate, *, employee_id: int):
        self.calls.append((book_data, employee_id))
        if self.error:
            raise self.error
        return SimpleNamespace(
            id=1,
            isbn=book_data.isbn,
            title=book_data.title,
            author=book_data.author,
            genre=book_data.genre,
        )


class FakeBookRepository:
    def __init__(self) -> None:
        self.has_employee = True
        self.existing_book = None
        self.created_with: BookCreate | None = None
        self.error: Exception | None = None

    def employee_exists(self, employee_id: int) -> bool:
        return self.has_employee

    def find_by_isbn(self, isbn: str):
        return self.existing_book

    def create_book(self, book_data: BookCreate):
        if self.error:
            raise self.error
        self.created_with = book_data
        return SimpleNamespace(id=1, **book_data.model_dump())


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _use_fake_service(error: Exception | None = None) -> FakeBookService:
    fake = FakeBookService(error)
    app.dependency_overrides[get_book_service] = lambda: fake
    return fake


def _authenticate_as(*role_codes: str, user_id: int = 41) -> None:
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=user_id,
        role_codes=list(role_codes),
    )


def _manual_payload() -> dict[str, str]:
    return {
        "isbn": "978-85-7522-553-0",
        "title": "Python Fluente",
        "author": "Luciano Ramalho",
        "genre": "Tecnologia",
    }


# ---- Controller ---------------------------------------------------------


def test_create_book_sem_token_retorna_401():
    _use_fake_service()

    response = client.post("/api/v1/books/", json=_manual_payload())

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


def test_create_book_com_role_insuficiente_retorna_403():
    _use_fake_service()
    _authenticate_as("USER")

    response = client.post("/api/v1/books/", json=_manual_payload())

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


@pytest.mark.parametrize("role", ["STOCK_KEEPER", "MANAGER", "ADMINISTRATOR"])
def test_roles_autorizadas_cadastram_obra(role):
    fake = _use_fake_service()
    _authenticate_as(role, user_id=73)

    response = client.post("/api/v1/books/", json=_manual_payload())

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "isbn": "9788575225530",
        "title": "Python Fluente",
        "author": "Luciano Ramalho",
        "genre": "Tecnologia",
    }
    assert fake.calls[0][1] == 73


def test_isbn_invalido_retorna_422_sem_chamar_service():
    fake = _use_fake_service()
    _authenticate_as("STOCK_KEEPER")

    response = client.post(
        "/api/v1/books/",
        json={**_manual_payload(), "isbn": "000-00-000-0000-0"},
    )

    assert response.status_code == 422
    assert fake.calls == []


def test_isbn_nao_encontrado_retorna_404_controlado():
    _use_fake_service(GoogleBooksNotFoundError())
    _authenticate_as("STOCK_KEEPER")

    response = client.post("/api/v1/books/", json={"isbn": "9788575225530"})

    assert response.status_code == 404
    assert response.json()["code"] == "google_books_not_found"


def test_isbn_duplicado_retorna_409_com_codigo_estavel():
    _use_fake_service(DuplicateIsbnError())
    _authenticate_as("MANAGER")

    response = client.post("/api/v1/books/", json=_manual_payload())

    assert response.status_code == 409
    assert response.json()["code"] == "duplicate_isbn"


# ---- Service ------------------------------------------------------------


def _service():
    db = MagicMock()
    repository = FakeBookRepository()
    return BookService(db=db, repository=repository), db, repository


@pytest.mark.anyio
async def test_dados_ausentes_sao_complementados_sem_mutar_entrada():
    service, db, repository = _service()
    original = BookCreate(isbn="978-85-7522-553-0")
    service.fetch_google_books_data = AsyncMock(
        return_value={
            "title": "Python Fluente",
            "author": "Luciano Ramalho",
            "genre": "Tecnologia",
        }
    )

    result = await service.create_book(original, employee_id=9)

    assert original.title is None
    assert repository.created_with == BookCreate(
        isbn="9788575225530",
        title="Python Fluente",
        author="Luciano Ramalho",
        genre="Tecnologia",
    )
    assert result.title == "Python Fluente"
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(result)


@pytest.mark.anyio
async def test_dados_manuais_nao_consultam_google_books():
    service, _db, repository = _service()
    service.fetch_google_books_data = AsyncMock()
    payload = BookCreate(**_manual_payload())

    await service.create_book(payload, employee_id=9)

    service.fetch_google_books_data.assert_not_awaited()
    assert repository.created_with == payload


@pytest.mark.anyio
async def test_usuario_com_role_mas_sem_employee_e_rejeitado_antes_da_insercao():
    service, db, repository = _service()
    repository.has_employee = False
    service.fetch_google_books_data = AsyncMock()

    with pytest.raises(EmployeeRecordRequiredError):
        await service.create_book(BookCreate(**_manual_payload()), employee_id=404)

    assert repository.created_with is None
    service.fetch_google_books_data.assert_not_awaited()
    db.execute.assert_not_called()
    db.rollback.assert_called_once_with()


@pytest.mark.anyio
async def test_contexto_de_auditoria_e_configurado_antes_do_insert_e_commit():
    events: list[str] = []
    service, db, repository = _service()
    db.execute.side_effect = lambda *_args, **_kwargs: events.append("context")
    db.commit.side_effect = lambda: events.append("commit")

    def create(book_data):
        events.append("insert")
        return SimpleNamespace(id=1, **book_data.model_dump())

    repository.create_book = create

    await service.create_book(BookCreate(**_manual_payload()), employee_id=27)

    assert events == ["context", "insert", "commit"]
    statement, parameters = db.execute.call_args.args
    assert "set_config" in str(statement)
    assert parameters == {"employee_id": "27"}


@pytest.mark.anyio
async def test_falha_de_persistencia_executa_rollback():
    service, db, repository = _service()
    repository.error = SQLAlchemyError("falha simulada")

    with pytest.raises(BookPersistenceError):
        await service.create_book(BookCreate(**_manual_payload()), employee_id=9)

    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


@pytest.mark.anyio
async def test_isbn_duplicado_detectado_pelo_banco_executa_rollback():
    service, db, repository = _service()
    repository.error = IntegrityError("insert", {}, Exception("unique"))

    with pytest.raises(DuplicateIsbnError):
        await service.create_book(BookCreate(**_manual_payload()), employee_id=9)

    db.rollback.assert_called_once_with()


@pytest.mark.anyio
async def test_google_books_sem_metadados_minimos_retorna_erro_controlado():
    service, db, _repository = _service()
    service.fetch_google_books_data = AsyncMock(return_value={"genre": "Tecnologia"})

    with pytest.raises(GoogleBooksInvalidResponseError):
        await service.create_book(BookCreate(isbn="9788575225530"), employee_id=9)

    db.rollback.assert_called_once_with()


@pytest.mark.anyio
async def test_timeout_do_google_books_e_traduzido_sem_requisicao_real(monkeypatch):
    service, _db, _repository = _service()

    class TimeoutClient:
        def __init__(self, *, timeout):
            assert timeout == 5.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            raise httpx.ReadTimeout("tempo esgotado")

    monkeypatch.setattr(httpx, "AsyncClient", TimeoutClient)

    with pytest.raises(GoogleBooksUnavailableError):
        await service.fetch_google_books_data("9788575225530")


# ---- Repository ---------------------------------------------------------


def test_repository_nao_controla_transacao():
    db = MagicMock()
    repository = BookRepository(db)

    book = repository.create_book(BookCreate(**_manual_payload()))

    db.add.assert_called_once_with(book)
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.refresh.assert_not_called()
