"""Testes do catálogo público e da administração de destaques.

Não dependem de banco: o service é substituído por um dublê via
`dependency_overrides`, e as regras puras (slug, agregação de ofertas) são
exercitadas direto.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import GenreNotFoundError
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_catalog_service
from app.main import app
from app.models.domain import CopyStatus, DestinationType
from app.schemas.catalog_schema import (
    BookOffer,
    CatalogBookResponse,
    FeaturedUpdate,
    GenreResponse,
    PagedBooksResponse,
)
from app.services.catalog_service import CatalogService, slugify

client = TestClient(app)


class FakeCatalogService:
    def __init__(self) -> None:
        self.featured_set: list[tuple[int, FeaturedUpdate]] = []

    def list_featured_books(self) -> list[CatalogBookResponse]:
        return [
            CatalogBookResponse(
                id=1,
                title="Dom Casmurro",
                author="Machado de Assis",
                cover_url=None,
                genres=["Ficção", "Romance"],
                offers=[
                    BookOffer(
                        destination=DestinationType.COMMERCIAL,
                        available=True,
                        price=Decimal("25.00"),
                    )
                ],
            )
        ]

    def list_featured_genres(self):
        return [SimpleNamespace(id=1, name="Ficção", slug="ficcao")]

    def list_books_by_genre(self, *, slug, page, page_size):
        if slug != "ficcao":
            raise GenreNotFoundError()
        return PagedBooksResponse(
            genre=GenreResponse(id=1, name="Ficção", slug="ficcao"),
            items=[],
            total=0,
            page=page,
            page_size=page_size,
        )

    def set_genre_featured(self, *, genre_id, data_in):
        self.featured_set.append((genre_id, data_in))
        return SimpleNamespace(id=genre_id, name="Ficção", slug="ficcao")


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()


def _use_fake_service() -> FakeCatalogService:
    fake = FakeCatalogService()
    app.dependency_overrides[get_catalog_service] = lambda: fake
    return fake


def _authenticate_as(*role_codes: str) -> None:
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1,
        name="Admin",
        email="admin@example.com",
        role_codes=list(role_codes),
    )


# ---- Catálogo público ----------------------------------------------------


def test_featured_books_dispensa_autenticacao():
    _use_fake_service()

    response = client.get("/api/v1/catalog/featured-books")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["title"] == "Dom Casmurro"
    # O livro carrega os dois gêneros: é o ganho do vínculo muitos-para-muitos.
    assert body[0]["genres"] == ["Ficção", "Romance"]
    assert body[0]["offers"][0]["destination"] == "COMMERCIAL"


def test_featured_genres_dispensa_autenticacao():
    _use_fake_service()

    response = client.get("/api/v1/catalog/genres")

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "name": "Ficção", "slug": "ficcao"}]


def test_genero_inexistente_retorna_404():
    _use_fake_service()

    response = client.get("/api/v1/catalog/genres/inexistente/books")

    assert response.status_code == 404
    assert response.json()["code"] == "genre_not_found"


def test_paginacao_rejeita_page_size_acima_do_teto():
    _use_fake_service()

    response = client.get("/api/v1/catalog/genres/ficcao/books?page_size=999")

    assert response.status_code == 422


# ---- Administração -------------------------------------------------------


def test_admin_sem_token_retorna_401():
    _use_fake_service()

    response = client.patch(
        "/api/v1/admin/genres/1/featured", json={"is_featured": True, "position": 1}
    )

    assert response.status_code == 401


def test_admin_com_papel_insuficiente_retorna_403():
    _use_fake_service()
    _authenticate_as("USER", "SELLER")

    response = client.patch(
        "/api/v1/admin/genres/1/featured", json={"is_featured": True, "position": 1}
    )

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_estoquista_nao_administra_destaque():
    """Estoquista cuida do acervo (US03), não da vitrine (US04)."""
    _use_fake_service()
    _authenticate_as("STOCK_KEEPER")

    response = client.patch(
        "/api/v1/admin/genres/1/featured", json={"is_featured": True, "position": 1}
    )

    assert response.status_code == 403


def test_administrador_altera_destaque():
    fake = _use_fake_service()
    _authenticate_as("ADMINISTRATOR")

    response = client.patch(
        "/api/v1/admin/genres/1/featured", json={"is_featured": True, "position": 2}
    )

    assert response.status_code == 200
    assert fake.featured_set == [(1, FeaturedUpdate(is_featured=True, position=2))]


# ---- Regras puras --------------------------------------------------------


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("Ficção", "ficcao"),
        ("Não ficção", "nao-ficcao"),
        ("Ação & Aventura", "acao-aventura"),
        ("  Suspense  ", "suspense"),
    ],
)
def test_slugify_preserva_a_letra_base_do_acento(nome, esperado):
    assert slugify(nome) == esperado


def _copy(destination, status=CopyStatus.AVAILABLE, price=None, is_active=True):
    return SimpleNamespace(
        destination=destination,
        status=status,
        sale_price=price,
        is_active=is_active,
    )


def test_ofertas_agregam_venda_e_emprestimo_do_mesmo_livro():
    book = SimpleNamespace(
        copies=[
            _copy(DestinationType.DIDACTIC),
            _copy(DestinationType.COMMERCIAL, price=Decimal("40.00")),
            _copy(DestinationType.COMMERCIAL, price=Decimal("25.00")),
        ]
    )

    offers = CatalogService._offers_for(book)

    # Venda primeiro, e pelo menor preço entre os exemplares.
    assert offers[0].destination == DestinationType.COMMERCIAL
    assert offers[0].price == Decimal("25.00")
    assert offers[0].available is True
    assert offers[1].destination == DestinationType.DIDACTIC
    assert offers[1].available is True


def test_livro_sem_exemplar_livre_fica_esgotado_e_nao_some():
    """US02: a vitrine sinaliza "Esgotado" em vez de omitir o título."""
    book = SimpleNamespace(
        copies=[_copy(DestinationType.COMMERCIAL, status=CopyStatus.SOLD, price=Decimal("30"))]
    )

    offers = CatalogService._offers_for(book)

    assert len(offers) == 1
    assert offers[0].available is False
    # O preço continua exposto: quem vê "Esgotado" ainda quer saber o valor.
    assert offers[0].price == Decimal("30")
    # Vendido não volta para a prateleira, então não cabe reserva.
    assert offers[0].can_reserve is False


def test_exemplar_de_venda_emprestado_habilita_reserva_de_compra():
    """RF07: exemplar destinado à venda que está emprestado admite reserva."""
    book = SimpleNamespace(
        copies=[
            _copy(DestinationType.COMMERCIAL, status=CopyStatus.BORROWED, price=Decimal("30"))
        ]
    )

    offers = CatalogService._offers_for(book)

    assert offers[0].available is False
    assert offers[0].can_reserve is True


def test_exemplar_inativo_nao_gera_oferta():
    book = SimpleNamespace(copies=[_copy(DestinationType.DIDACTIC, is_active=False)])

    assert CatalogService._offers_for(book) == []


# ---- Cadastro de funcionário (RF06) --------------------------------------


def test_cadastro_de_funcionario_exige_sessao():
    response = client.post(
        "/api/v1/employees/",
        json={"name": "X", "email": "x@libstock.com.br", "password": "senha123",
              "accessLevel": "Vendedor"},
    )

    assert response.status_code == 401


def test_cadastro_de_funcionario_recusa_papel_comum():
    """Definir nível de acesso é privativo do administrador (RF06)."""
    _authenticate_as("SELLER")

    response = client.post(
        "/api/v1/employees/",
        json={"name": "X", "email": "x@libstock.com.br", "password": "senha123",
              "accessLevel": "Vendedor"},
    )

    assert response.status_code == 403


def test_cadastro_de_funcionario_aceita_administrador():
    _authenticate_as("ADMINISTRATOR")

    response = client.post(
        "/api/v1/employees/",
        json={"name": "X", "email": "x@libstock.com.br", "password": "senha123",
              "accessLevel": "Vendedor"},
    )

    assert response.status_code == 201
