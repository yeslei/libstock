"""Testes unitários e de integração do cadastro de obras."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    BookPersistenceError,
    DuplicateIsbnError,
    DuplicateBarcodeError,
    EmployeeRecordRequiredError,
    GoogleBooksInvalidResponseError,
    GoogleBooksNotFoundError,
    GoogleBooksRateLimitError,
    GoogleBooksUnavailableError,
)
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_book_service
from app.core.database import engine
from app.main import app
from app.models.domain import AuditLog, Book, Copy, Employee
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
            is_active=True,
            initial_copy=SimpleNamespace(
                id=2,
                book_id=1,
                status="AVAILABLE",
                is_active=True,
                **book_data.initial_copy.model_dump(),
            ),
        )


class FakeBookRepository:
    def __init__(self) -> None:
        self.has_employee = True
        self.existing_book = None
        self.created_with: BookCreate | None = None
        self.error: Exception | None = None
        self.existing_copy = None
        self.created_copy = None

    def employee_exists(self, employee_id: int) -> bool:
        return self.has_employee

    def find_by_isbn(self, isbn: str):
        return self.existing_book

    def find_copy_by_barcode(self, barcode: str):
        return self.existing_copy

    def create_book(self, book_data: BookCreate):
        if self.error:
            raise self.error
        self.created_with = book_data
        return SimpleNamespace(
            id=1,
            is_active=True,
            **book_data.model_dump(exclude={"initial_copy"}),
        )

    def create_copy(self, book_id, copy_data):
        if self.error:
            raise self.error
        self.created_copy = SimpleNamespace(
            id=2,
            book_id=book_id,
            status="AVAILABLE",
            is_active=True,
            **copy_data.model_dump(),
        )
        return self.created_copy


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
        "initial_copy": {
            "barcode": "EX-0001",
            "destination": "DIDACTIC",
            "condition": "NOVO",
            "sale_price": None,
            "acquired_at": "2026-09-06",
        },
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
        "is_active": True,
        "initial_copy": {
            "id": 2,
            "book_id": 1,
            "barcode": "EX-0001",
            "destination": "DIDACTIC",
            "status": "AVAILABLE",
            "condition": "NOVO",
            "sale_price": None,
            "acquired_at": "2026-09-06",
            "is_active": True,
        },
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

    payload = _manual_payload()
    payload["title"] = None
    payload["author"] = None
    response = client.post("/api/v1/books/", json=payload)

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
    original = BookCreate(
        isbn="978-85-7522-553-0", initial_copy=_manual_payload()["initial_copy"]
    )
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
        initial_copy=_manual_payload()["initial_copy"],
    )
    assert result.title == "Python Fluente"
    db.commit.assert_called_once_with()
    db.refresh.assert_not_called()
    assert result.initial_copy.book_id == result.id


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
        return SimpleNamespace(
            id=1, is_active=True, **book_data.model_dump(exclude={"initial_copy"})
        )

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
    origin = SimpleNamespace(diag=SimpleNamespace(constraint_name="books_isbn_key"))
    repository.error = IntegrityError("insert", {}, origin)

    with pytest.raises(DuplicateIsbnError):
        await service.create_book(BookCreate(**_manual_payload()), employee_id=9)

    db.rollback.assert_called_once_with()


@pytest.mark.anyio
async def test_barcode_duplicado_detectado_pela_constraint_exata():
    service, db, repository = _service()
    origin = SimpleNamespace(diag=SimpleNamespace(constraint_name="copies_barcode_key"))
    repository.error = IntegrityError("insert", {}, origin)

    with pytest.raises(DuplicateBarcodeError):
        await service.create_book(BookCreate(**_manual_payload()), employee_id=9)

    db.rollback.assert_called_once_with()


@pytest.mark.anyio
async def test_outra_constraint_com_nome_da_coluna_nao_vira_duplicidade():
    service, db, repository = _service()
    origin = SimpleNamespace(
        diag=SimpleNamespace(constraint_name="chk_copies_barcode_format"),
        __str__=lambda _self: "violates check constraint; column copies.barcode",
    )
    repository.error = IntegrityError("insert", {}, origin)

    with pytest.raises(BookPersistenceError):
        await service.create_book(BookCreate(**_manual_payload()), employee_id=9)

    db.rollback.assert_called_once_with()


@pytest.mark.anyio
async def test_integrity_error_desconhecido_vira_erro_de_persistencia():
    service, db, repository = _service()
    repository.error = IntegrityError("insert", {}, Exception("integrity failure"))

    with pytest.raises(BookPersistenceError):
        await service.create_book(BookCreate(**_manual_payload()), employee_id=9)

    db.rollback.assert_called_once_with()


@pytest.mark.anyio
async def test_google_books_sem_metadados_minimos_retorna_erro_controlado():
    service, db, _repository = _service()
    service.fetch_google_books_data = AsyncMock(return_value={"genre": "Tecnologia"})

    with pytest.raises(GoogleBooksInvalidResponseError):
        await service.create_book(
            BookCreate(isbn="9788575225530", initial_copy=_manual_payload()["initial_copy"]),
            employee_id=9,
        )

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


@pytest.mark.anyio
async def test_google_books_429_tem_erro_publico_controlado(monkeypatch):
    service, _db, _repository = _service()

    class RateLimitedClient:
        def __init__(self, *, timeout):
            assert timeout == 5.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, request_url, **_kwargs):
            request = httpx.Request("GET", request_url)
            return httpx.Response(429, request=request)

    monkeypatch.setattr(httpx, "AsyncClient", RateLimitedClient)

    with pytest.raises(GoogleBooksRateLimitError) as raised:
        await service.fetch_google_books_data("9788575225530")

    assert raised.value.code == "google_books_rate_limited"
    assert raised.value.status_code == 503


@pytest.mark.anyio
async def test_codigo_de_barras_duplicado_e_distinto_de_isbn():
    service, db, repository = _service()
    repository.existing_copy = object()

    with pytest.raises(DuplicateBarcodeError):
        await service.create_book(BookCreate(**_manual_payload()), employee_id=9)

    assert repository.created_with is None
    db.rollback.assert_called_once_with()


@pytest.mark.anyio
async def test_falha_ao_inserir_exemplar_desfaz_toda_a_transacao():
    service, db, repository = _service()

    def fail_copy(_book_id, _copy_data):
        raise SQLAlchemyError("falha no exemplar")

    repository.create_copy = fail_copy

    with pytest.raises(BookPersistenceError):
        await service.create_book(BookCreate(**_manual_payload()), employee_id=9)

    assert repository.created_with is not None
    db.commit.assert_not_called()
    db.rollback.assert_called_once_with()


@pytest.mark.anyio
async def test_falha_no_commit_desfaz_obra_exemplar_e_auditoria():
    service, db, repository = _service()
    db.commit.side_effect = SQLAlchemyError("falha no commit")

    with pytest.raises(BookPersistenceError):
        await service.create_book(BookCreate(**_manual_payload()), employee_id=9)

    assert repository.created_with is not None
    assert repository.created_copy.book_id == 1
    db.commit.assert_called_once_with()
    db.rollback.assert_called_once_with()


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


@pytest.mark.anyio
async def test_postgresql_aceita_obra_e_exemplar_e_rollback_nao_deixa_parcial(request):
    """Exercita os triggers diferidos e de auditoria no PostgreSQL migrado."""
    def unique_isbn() -> str:
        body = "978" + f"{uuid4().int % 1_000_000_000:09d}"
        checksum = (10 - sum(int(digit) * (1 if index % 2 == 0 else 3) for index, digit in enumerate(body)) % 10) % 10
        return f"{body}{checksum}"

    first_isbn = unique_isbn()
    second_isbn = unique_isbn()
    barcode = f"IT-BOOK-{uuid4().hex}"
    first_book_id: int | None = None
    first_copy_id: int | None = None
    employee_id: int | None = None

    def cleanup_created_records() -> None:
        if first_book_id is None or first_copy_id is None or employee_id is None:
            return
        with engine.begin() as cleanup:
            cleanup.execute(
                text("SELECT set_config('libstock.employee_id', :employee_id, true)"),
                {"employee_id": str(employee_id)},
            )
            cleanup.execute(delete(Copy).where(Copy.id == first_copy_id))
            cleanup.execute(delete(Book).where(Book.id == first_book_id))
            cleanup.execute(
                text(
                    "ALTER TABLE audit_logs DISABLE TRIGGER "
                    "trg_prevent_audit_log_modification"
                )
            )
            cleanup.execute(
                delete(AuditLog).where(
                    ((AuditLog.entity_type == "books") & (AuditLog.entity_id == str(first_book_id)))
                    | ((AuditLog.entity_type == "copies") & (AuditLog.entity_id == str(first_copy_id)))
                )
            )
            cleanup.execute(
                text(
                    "ALTER TABLE audit_logs ENABLE TRIGGER "
                    "trg_prevent_audit_log_modification"
                )
            )

    request.addfinalizer(cleanup_created_records)

    db = Session(bind=engine, expire_on_commit=False)
    try:
        employee_id = db.scalar(select(Employee.id).order_by(Employee.id).limit(1))
        assert employee_id is not None, "O banco de integração precisa de um funcionário."
        assert db.scalar(select(Book.id).where(Book.isbn.in_([first_isbn, second_isbn]))) is None
        assert db.scalar(select(Copy.id).where(Copy.barcode == barcode)) is None

        service = BookService(db=db, repository=BookRepository(db))
        first = await service.create_book(
            BookCreate.model_validate(
                {
                    "isbn": first_isbn,
                    "title": "Clean Code",
                    "author": "Robert C. Martin",
                    "initial_copy": {
                        "barcode": barcode,
                        "destination": "DIDACTIC",
                    },
                }
            ),
            employee_id=employee_id,
        )

        assert first.initial_copy is not None
        first_book_id = first.id
        first_copy_id = first.initial_copy.id
        assert first.is_active is True
        assert first.initial_copy.is_active is True
        assert first.initial_copy.status.value == "AVAILABLE"
        assert first.initial_copy.book_id == first.id

        # O commit do service encerra a transação e, portanto, obriga o
        # PostgreSQL a avaliar o constraint trigger diferido da obra ativa.
        with Session(bind=engine) as committed:
            committed_book = committed.scalar(select(Book).where(Book.id == first.id))
            committed_copy = committed.scalar(select(Copy).where(Copy.id == first_copy_id))
            assert committed_book is not None and committed_book.is_active is True
            assert committed_copy is not None
            assert committed_copy.book_id == first.id
            assert committed_copy.is_active is True
            assert committed_copy.status.value == "AVAILABLE"

            audits = committed.scalars(
                select(AuditLog).where(
                    AuditLog.employee_id == employee_id,
                    ((
                        (AuditLog.entity_type == "books")
                        & (AuditLog.entity_id == str(first.id))
                    )
                    | (
                        (AuditLog.entity_type == "copies")
                        & (AuditLog.entity_id == str(first_copy_id))
                    )),
                )
            ).all()
            assert {(audit.entity_type, audit.entity_id, audit.operation) for audit in audits} == {
                ("books", str(first.id), "INSERT"),
                ("copies", str(first_copy_id), "INSERT"),
            }

        class ConstraintOnlyRepository(BookRepository):
            def find_copy_by_barcode(self, _barcode: str):
                # Simula a corrida entre o pre-check e o INSERT: a garantia
                # definitiva precisa vir da UNIQUE real no PostgreSQL.
                return None

        rollback_service = BookService(
            db=db, repository=ConstraintOnlyRepository(db)
        )
        with pytest.raises(DuplicateBarcodeError):
            await rollback_service.create_book(
                BookCreate.model_validate(
                    {
                        "isbn": second_isbn,
                        "title": "The Pragmatic Programmer",
                        "author": "Andrew Hunt, David Thomas",
                        "initial_copy": {
                            "barcode": barcode,
                            "destination": "DIDACTIC",
                        },
                    }
                ),
                employee_id=employee_id,
            )
    finally:
        db.close()

    with engine.connect() as verification:
        assert verification.scalar(select(Book.id).where(Book.isbn == second_isbn)) is None
        assert verification.scalar(
            select(Copy.id).join(Book).where(Book.isbn == second_isbn)
        ) is None
        assert verification.scalar(
            select(AuditLog.id).where(
                AuditLog.new_value["isbn"].as_string() == second_isbn
            )
        ) is None
