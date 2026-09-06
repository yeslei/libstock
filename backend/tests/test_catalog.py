"""Testes do catálogo público e da administração de destaques.

Não dependem de banco: o service é substituído por um dublê via
`dependency_overrides`, e as regras puras (slug, agregação de ofertas) são
exercitadas direto.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.exceptions import AuditActorRequiredError, GenreNotFoundError
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_catalog_service
from app.main import app
from app.models.domain import Book, BookGenre, Copy, CopyStatus, DestinationType, Genre
from app.repositories.catalog_repository import CatalogRepository
from app.schemas.catalog_schema import (
    BookOffer,
    CatalogBookResponse,
    FeaturedUpdate,
    GenreResponse,
    PagedBooksResponse,
    CatalogSearchParams,
)
from app.services.catalog_service import CatalogService, slugify

client = TestClient(app)


class FakeCatalogService:
    def __init__(self) -> None:
        self.featured_set: list[tuple[int, FeaturedUpdate]] = []
        self.last_search: dict[str, object] | None = None
        self.book_featured_set: list[tuple[int, FeaturedUpdate, int]] = []

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

    def search_books(self, *, title=None, author=None, isbn=None, barcode=None):
        self.last_search = {
            "title": title,
            "author": author,
            "isbn": isbn,
            "barcode": barcode,
        }
        return [
            CatalogBookResponse(
                id=1,
                title=title or "Dom Casmurro",
                author=author or "Machado de Assis",
            )
        ]

    def set_genre_featured(self, *, genre_id, data_in):
        self.featured_set.append((genre_id, data_in))
        return SimpleNamespace(id=genre_id, name="Ficção", slug="ficcao")

    def set_book_featured(self, *, book_id, data_in, actor_id):
        self.book_featured_set.append((book_id, data_in, actor_id))
        return SimpleNamespace(
            id=book_id, title="Dom Casmurro", author="Machado de Assis",
            cover_url=None, genres=[],
        )


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


def test_busca_por_autor_no_catalogo_dispensa_autenticacao():
    _use_fake_service()

    response = client.get("/api/v1/catalog/books?author=%20machado%20")

    assert response.status_code == 200
    assert response.json()[0]["author"] == "machado"


def test_busca_no_catalogo_exige_titulo_ou_autor():
    _use_fake_service()

    response = client.get("/api/v1/catalog/books")

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("query", "criterion", "value"),
    [("isbn=978-85-1", "isbn", "978-85-1"), ("barcode=BC-1", "barcode", "BC-1")],
)
def test_busca_por_identificador_no_catalogo(query, criterion, value):
    fake = _use_fake_service()
    response = client.get(f"/api/v1/catalog/books?{query}")
    assert response.status_code == 200
    assert fake.last_search == {
        "title": None,
        "author": None,
        "isbn": value if criterion == "isbn" else None,
        "barcode": value if criterion == "barcode" else None,
    }


def test_identificador_em_branco_e_invalido():
    with pytest.raises(ValueError):
        CatalogSearchParams(isbn="   ")


@pytest.mark.parametrize(
    "field, method, value",
    [
        ("isbn", "search_by_isbn", "978-85-1"),
        ("barcode", "search_by_barcode", "BC-1"),
    ],
)
def test_service_delega_busca_por_identificador(field, method, value):
    repository = Mock(spec=CatalogRepository)
    getattr(repository, method).return_value = []
    service = CatalogService(db=Mock(), catalog_repository=repository, genre_repository=Mock())
    assert service.search_books(**{field: value}) == []
    getattr(repository, method).assert_called_once_with(value)


class TestCatalogRepositorySearch:
    def setup_method(self):
        self.engine = create_engine("sqlite:///:memory:")
        for table in (Book.__table__, Genre.__table__, BookGenre.__table__, Copy.__table__):
            table.create(self.engine)
        self.db = Session(self.engine)
        self.db.add_all(
            [
                Book(id=1, isbn="978-85-1", title="Livro ISBN", author="Autor", is_active=True),
                Book(id=2, isbn="978-85-2", title="Livro inativo", author="Autor", is_active=False),
                Book(id=3, isbn="978-85-3", title="Livro sem cópia ativa", author="Autor", is_active=True),
            ]
        )
        self.db.flush()
        self.db.add_all(
            [
                Copy(id=1, book_id=1, barcode="BC-1", destination=DestinationType.DIDACTIC, is_active=True),
                Copy(id=2, book_id=2, barcode="BC-2", destination=DestinationType.DIDACTIC, is_active=True),
                Copy(id=3, book_id=3, barcode="BC-3", destination=DestinationType.DIDACTIC, is_active=False),
            ]
        )
        self.db.commit()
        self.repository = CatalogRepository(self.db)

    def teardown_method(self):
        self.db.close()
        self.engine.dispose()

    def test_isbn_exact_match_and_non_match(self):
        assert [book.id for book in self.repository.search_by_isbn("978-85-1")] == [1]
        assert self.repository.search_by_isbn("978-85") == []

    def test_barcode_exact_match_and_inactive_copy_excluded(self):
        assert [book.id for book in self.repository.search_by_barcode("BC-1")] == [1]
        assert self.repository.search_by_barcode("BC") == []
        assert self.repository.search_by_barcode("BC-3") == []

    def test_catalog_visibility_excludes_inactive_or_copyless_books(self):
        assert self.repository.search_by_isbn("978-85-2") == []
        assert self.repository.search_by_isbn("978-85-3") == []
        assert self.repository.search_by_barcode("unknown") == []


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


# ---- Auditoria de inventário (RNF03) -------------------------------------


class FakeCatalogRepository:
    """Dublê que registra a ordem das chamadas.

    A ordem importa: `books` é tabela auditada e o banco recusa a escrita se
    o contexto do funcionário não vier antes dela.
    """

    def __init__(self, *, employee: bool = True) -> None:
        self.employee = employee
        self.chamadas: list[str] = []
        self.book = SimpleNamespace(
            id=7, title="Dom Casmurro", author="Machado de Assis", cover_url=None,
            genres=[], is_featured=False, featured_position=None,
        )

    def is_employee(self, user_id):
        self.chamadas.append(f"is_employee({user_id})")
        return self.employee

    def set_audit_actor(self, employee_id):
        self.chamadas.append(f"set_audit_actor({employee_id})")

    def find_book_by_id(self, book_id):
        self.chamadas.append(f"find_book_by_id({book_id})")
        return self.book


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self):
        self.commits += 1

    def refresh(self, _obj):
        pass


def _servico_com(repositorio) -> CatalogService:
    return CatalogService(
        db=FakeSession(),
        catalog_repository=repositorio,
        genre_repository=None,
    )


def test_destaque_de_livro_abre_o_contexto_de_auditoria_antes_de_escrever():
    repositorio = FakeCatalogRepository()

    livro = _servico_com(repositorio).set_book_featured(
        book_id=7, data_in=FeaturedUpdate(is_featured=True, position=2), actor_id=42
    )

    assert livro.is_featured is True
    assert livro.featured_position == 2
    # Sem o set_audit_actor antes da escrita, o trigger de auditoria recusa
    # o UPDATE e a rota devolve 500.
    assert repositorio.chamadas == [
        "is_employee(42)",
        "set_audit_actor(42)",
        "find_book_by_id(7)",
    ]


def test_destaque_de_livro_recusa_ator_sem_vinculo_de_funcionario():
    repositorio = FakeCatalogRepository(employee=False)

    with pytest.raises(AuditActorRequiredError):
        _servico_com(repositorio).set_book_featured(
            book_id=7, data_in=FeaturedUpdate(is_featured=True, position=1), actor_id=99
        )

    assert "set_audit_actor(99)" not in repositorio.chamadas


def test_rota_de_destaque_repassa_o_usuario_autenticado():
    fake = _use_fake_service()
    _authenticate_as("ADMINISTRATOR")

    response = client.patch(
        "/api/v1/admin/books/7/featured", json={"is_featured": True, "position": 3}
    )

    assert response.status_code == 200
    _, _, actor_id = fake.book_featured_set[0]
    assert actor_id == 1  # id do usuário autenticado no dublê
