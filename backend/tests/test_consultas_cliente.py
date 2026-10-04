"""Consultas do cliente (Issue #153): contratos HTTP e regras sem banco."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.controllers.client_eligibility_controller import get_client_eligibility_service
from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_catalog_service
from app.main import app
from app.schemas.catalog_schema import PagedCatalogResponse
from app.schemas.client_eligibility_schema import EligibilityReason, EligibilityResponse
from app.services.catalog_service import CatalogService
from app.services.client_eligibility import ClientEligibilityService

http = TestClient(app)


@pytest.fixture(autouse=True)
def _reset():
    yield
    app.dependency_overrides.clear()


def test_acervo_completo_e_publico_e_repassa_parametros():
    fake = Mock()
    fake.list_all_books.return_value = PagedCatalogResponse(items=[], total=0, page=2, page_size=24)
    app.dependency_overrides[get_catalog_service] = lambda: fake
    response = http.get("/api/v1/catalog/books/all?page=2&page_size=24&q=dom")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 2, "page_size": 24}
    fake.list_all_books.assert_called_once_with(page=2, page_size=24, q="dom")


@pytest.mark.parametrize("query", ["page=0", "page_size=0", "page_size=49", "q=" + "x" * 101])
def test_acervo_completo_valida_entrada(query):
    app.dependency_overrides[get_catalog_service] = lambda: Mock()
    assert http.get(f"/api/v1/catalog/books/all?{query}").status_code == 422


def test_genres_all_escolhe_todas_ou_destaques():
    fake = Mock()
    fake.list_featured_genres.return_value = [NS(id=1, name="A", slug="a")]
    fake.list_all_genres.return_value = [NS(id=1, name="A", slug="a"), NS(id=2, name="B", slug="b")]
    app.dependency_overrides[get_catalog_service] = lambda: fake
    assert len(http.get("/api/v1/catalog/genres").json()) == 1
    assert len(http.get("/api/v1/catalog/genres?all=true").json()) == 2
    assert len(http.get("/api/v1/catalog/genres?all=false").json()) == 1


def test_service_normaliza_busca_em_branco_no_acervo():
    repository = Mock()
    repository.find_all_books.return_value = ([], 0)
    service = CatalogService(db=Mock(), catalog_repository=repository, genre_repository=Mock())
    result = service.list_all_books(page=1, page_size=12, q="   ")
    assert result.total == 0 and result.items == []
    assert repository.find_all_books.call_args.kwargs["q"] is None


def test_elegibilidade_exige_sessao_e_papel_user():
    fake = Mock()
    app.dependency_overrides[get_client_eligibility_service] = lambda: fake
    assert http.get("/api/v1/me/eligibility").status_code == 401
    app.dependency_overrides[get_current_user] = lambda: NS(id=3, role_codes=["SELLER"])
    assert http.get("/api/v1/me/eligibility").status_code == 403
    fake.check.assert_not_called()


def test_elegibilidade_usa_a_identidade_autenticada():
    fake = Mock()
    fake.check.return_value = EligibilityResponse(
        eligible=False, reasons=[EligibilityReason(code="penalized", message="Cliente com penalidade ativa.")])
    app.dependency_overrides[get_client_eligibility_service] = lambda: fake
    app.dependency_overrides[get_current_user] = lambda: NS(id=7, role_codes=["USER"])
    response = http.get("/api/v1/me/eligibility?client_id=99")
    assert response.status_code == 200
    assert response.json() == {"eligible": False, "reasons": [{"code": "penalized", "message": "Cliente com penalidade ativa."}]}
    fake.check.assert_called_once_with(7)


def _records(*, profile=True, user=True, penalized=False):
    return (NS(is_penalized=penalized), NS(is_active=profile), NS(is_active=user))


@pytest.mark.parametrize("kwargs,overdue,expected", [
    ({}, False, []),
    ({"profile": False}, False, ["inactive"]),
    ({"user": False}, False, ["inactive"]),
    ({"penalized": True}, False, ["penalized"]),
    ({}, True, ["overdue_loan"]),
    ({"user": False, "penalized": True}, True, ["inactive", "penalized", "overdue_loan"]),
])
def test_service_deriva_motivos_do_predicado_compartilhado(kwargs, overdue, expected):
    repository = Mock()
    repository.find_client.return_value = _records(**kwargs)
    repository.has_overdue_loan.return_value = overdue
    result = ClientEligibilityService(repository).check(5)
    assert [r.code for r in result.reasons] == expected
    assert result.eligible is (not expected)
    repository.lock_client.assert_not_called()


def test_service_cliente_inexistente_e_403():
    repository = Mock()
    repository.find_client.return_value = None
    with pytest.raises(Exception) as error:
        ClientEligibilityService(repository).check(5)
    assert error.value.status_code == 403 and error.value.code == "client_required"
