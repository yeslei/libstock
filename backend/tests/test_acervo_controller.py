from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import (
    AcervoItemNotFoundError,
    BookNotFoundError,
    DestinationTagNotFoundError,
    DuplicateIsbnError,
)
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_acervo_service
from app.main import app
from app.schemas.acervo_schema import ClassifyItemInput
from app.schemas.book_schema import BookUpdate

client = TestClient(app)


class FakeAcervoService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[int, ClassifyItemInput, int]] = []
        self.update_calls: list[tuple[int, BookUpdate, int | None]] = []

    def classify_item(self, item_id: int, payload: ClassifyItemInput, *, actor_id: int):
        self.calls.append((item_id, payload, actor_id))
        if self.error:
            raise self.error
        tag_id = payload.tag_id or 1
        tag_name = payload.tag_name or "Doação"
        return SimpleNamespace(
            id=item_id,
            book_id=10,
            barcode="BC-12345",
            status="AVAILABLE",
            destination="DIDACTIC",
            destination_tag=SimpleNamespace(
                id=tag_id,
                name=tag_name,
                slug="doacao",
                description="Destinado a doação",
            ),
        )

    def list_tags(self):
        return [
            SimpleNamespace(id=1, name="Doação", slug="doacao", description=None),
            SimpleNamespace(id=2, name="Descarte", slug="descarte", description=None),
            SimpleNamespace(id=3, name="Venda", slug="venda", description=None),
            SimpleNamespace(id=4, name="Acervo Fixo", slug="acervo-fixo", description=None),
        ]

    def get_item(self, item_id: int):
        if self.error:
            raise self.error
        return SimpleNamespace(
            id=item_id,
            book_id=10,
            barcode="BC-12345",
            status="AVAILABLE",
            destination="DIDACTIC",
            destination_tag=None,
        )

    def update_book(self, book_id: int, payload: BookUpdate, *, actor_id: int | None = None):
        self.update_calls.append((book_id, payload, actor_id))
        if self.error:
            raise self.error
        return SimpleNamespace(
            id=book_id,
            isbn=payload.isbn or "9788575225530",
            title=payload.title or "Título Atualizado",
            author=payload.author or "Autor Atualizado",
            genre=payload.genre or "Ficção",
            is_active=payload.is_active if payload.is_active is not None else True,
            initial_copy=None,
        )


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()


def _use_fake_service(error: Exception | None = None) -> FakeAcervoService:
    fake = FakeAcervoService(error)
    app.dependency_overrides[get_acervo_service] = lambda: fake
    return fake


def _authenticate_as(*role_codes: str, user_id: int = 42) -> None:
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=user_id,
        name="Test User",
        email="user@example.com",
        role_codes=list(role_codes),
    )


# ---- Autenticação e Autorização ----


def test_classify_item_sem_token_retorna_401():
    _use_fake_service()
    response = client.post("/api/v1/acervo/1/tags", json={"tag_id": 1})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


def test_classify_item_role_insuficiente_retorna_403():
    _use_fake_service()
    _authenticate_as("USER")
    response = client.post("/api/v1/acervo/1/tags", json={"tag_id": 1})
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_classify_item_role_seller_retorna_403():
    _use_fake_service()
    _authenticate_as("SELLER")
    response = client.patch("/api/v1/acervo/1/destinacao", json={"tag_name": "Doação"})
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


# ---- Casos de Sucesso ----


@pytest.mark.parametrize("role", ["STOCK_KEEPER", "ADMINISTRATOR"])
def test_classify_item_sucesso_post_tags(role):
    fake = _use_fake_service()
    _authenticate_as(role, user_id=15)

    response = client.post("/api/v1/acervo/7/tags", json={"tag_id": 2})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 7
    assert data["destination_tag"]["id"] == 2
    assert fake.calls[0] == (7, ClassifyItemInput(tag_id=2), 15)


@pytest.mark.parametrize("role", ["STOCK_KEEPER", "ADMINISTRATOR"])
def test_classify_item_sucesso_patch_destinacao(role):
    fake = _use_fake_service()
    _authenticate_as(role, user_id=20)

    response = client.patch("/api/v1/acervo/8/destinacao", json={"tag_name": "Descarte"})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 8
    assert data["destination_tag"]["name"] == "Descarte"
    assert fake.calls[0] == (8, ClassifyItemInput(tag_name="Descarte"), 20)


# ---- Casos de Erro de Domínio e Validação ----


def test_classify_item_inexistente_retorna_404():
    _use_fake_service(AcervoItemNotFoundError())
    _authenticate_as("STOCK_KEEPER")

    response = client.post("/api/v1/acervo/999/tags", json={"tag_id": 1})

    assert response.status_code == 404
    assert response.json()["code"] == "item_not_found"


def test_classify_item_tag_inexistente_retorna_404():
    _use_fake_service(DestinationTagNotFoundError())
    _authenticate_as("STOCK_KEEPER")

    response = client.post("/api/v1/acervo/1/tags", json={"tag_name": "TagInexistente"})

    assert response.status_code == 404
    assert response.json()["code"] == "destination_tag_not_found"


def test_classify_item_payload_invalido_retorna_422():
    _use_fake_service()
    _authenticate_as("STOCK_KEEPER")

    response = client.post("/api/v1/acervo/1/tags", json={})

    assert response.status_code == 422


def test_classify_item_payload_tag_name_vazio_retorna_422():
    _use_fake_service()
    _authenticate_as("STOCK_KEEPER")

    response = client.post("/api/v1/acervo/1/tags", json={"tag_name": "   "})

    assert response.status_code == 422


# ---- Endpoints Auxiliares ----


def test_list_destination_tags():
    _use_fake_service()
    _authenticate_as("STOCK_KEEPER")

    response = client.get("/api/v1/acervo/tags")

    assert response.status_code == 200
    tags = response.json()
    assert len(tags) == 4
    assert tags[0]["slug"] == "doacao"


def test_get_acervo_item():
    _use_fake_service()
    _authenticate_as("ADMINISTRATOR")

    response = client.get("/api/v1/acervo/5")

    assert response.status_code == 200
    assert response.json()["id"] == 5


# ---- Atualização de Obra do Acervo (EAP-1.3.3 / Issue #18) ----


def test_update_acervo_book_sem_token_retorna_401():
    _use_fake_service()
    response = client.patch("/api/v1/acervo/1", json={"title": "Novo Título"})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


def test_update_acervo_book_role_insuficiente_retorna_403():
    _use_fake_service()
    _authenticate_as("USER")
    response = client.patch("/api/v1/acervo/1", json={"title": "Novo Título"})
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


@pytest.mark.parametrize("role", ["STOCK_KEEPER", "ADMINISTRATOR", "MANAGER"])
def test_update_acervo_book_sucesso_prefixo_api(role):
    fake = _use_fake_service()
    _authenticate_as(role, user_id=10)

    response = client.patch("/api/v1/acervo/42", json={"title": "Clean Architecture", "genre": "Tecnologia"})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 42
    assert data["title"] == "Clean Architecture"
    assert data["genre"] == "Tecnologia"
    assert len(fake.update_calls) == 1
    assert fake.update_calls[0][0] == 42
    assert fake.update_calls[0][1].title == "Clean Architecture"
    assert fake.update_calls[0][2] == 10


def test_update_acervo_book_sucesso_rota_direta():
    fake = _use_fake_service()
    _authenticate_as("STOCK_KEEPER", user_id=10)

    response = client.patch("/acervo/42", json={"title": "Clean Code"})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 42
    assert data["title"] == "Clean Code"
    assert len(fake.update_calls) == 1


def test_update_acervo_book_inexistente_retorna_404():
    _use_fake_service(BookNotFoundError())
    _authenticate_as("STOCK_KEEPER")

    response = client.patch("/api/v1/acervo/999", json={"title": "Título"})

    assert response.status_code == 404
    assert response.json()["code"] == "book_not_found"


def test_update_acervo_book_isbn_duplicado_retorna_409():
    _use_fake_service(DuplicateIsbnError())
    _authenticate_as("STOCK_KEEPER")

    response = client.patch("/api/v1/acervo/1", json={"isbn": "978-85-7522-553-0"})

    assert response.status_code == 409
    assert response.json()["code"] == "duplicate_isbn"


def test_update_acervo_book_titulo_vazio_retorna_422():
    _use_fake_service()
    _authenticate_as("STOCK_KEEPER")

    response = client.patch("/api/v1/acervo/1", json={"title": "   "})

    assert response.status_code == 422


def test_update_acervo_book_isbn_invalido_retorna_422():
    _use_fake_service()
    _authenticate_as("STOCK_KEEPER")

    response = client.patch("/api/v1/acervo/1", json={"isbn": "isbn-invalido"})

    assert response.status_code == 422


def test_update_acervo_book_ano_invalido_retorna_422():
    _use_fake_service()
    _authenticate_as("STOCK_KEEPER")

    response = client.patch("/api/v1/acervo/1", json={"publication_year": 999})

    assert response.status_code == 422


def test_update_acervo_book_campo_extra_retorna_422():
    _use_fake_service()
    _authenticate_as("STOCK_KEEPER")

    response = client.patch("/api/v1/acervo/1", json={"extra_field": "invalido"})

    assert response.status_code == 422

