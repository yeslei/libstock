"""Consultas do cliente (Issue #153) contra PostgreSQL migrado (LIBSTOCK_V2_TEST_DATABASE_URL)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.authentication import get_current_user
from app.main import app
from app.models.domain import (
    Book, BookGenre, Client, Copy, DestinationType, Employee, Genre, Loan, LoanStatus, Profile,
)
from app.models.user import User
from app.repositories.catalog_repository import CatalogRepository, GenreRepository
from app.repositories.client_request_repository import ClientRequestRepository
from app.services.catalog_service import CatalogService
from app.services.client_eligibility import ClientEligibilityService
from test_client_requests_postgres import records  # noqa: F401  (fixture)


def _audit(db):
    admin = db.scalar(select(Employee.id).order_by(Employee.id))
    db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {"id": str(admin)})
    return admin


def _book(db, title, *, active=True, copies=1, genre=None):
    book = Book(title=title, author="Autora Consulta", is_active=active)
    db.add(book)
    db.flush()
    for _ in range(copies):
        db.add(Copy(book_id=book.id, barcode=uuid4().hex, destination=DestinationType.DIDACTIC))
    if genre:
        db.add(BookGenre(book_id=book.id, genre_id=genre.id))
    db.flush()
    return book


def _catalog(db):
    return CatalogService(db=db, catalog_repository=CatalogRepository(db), genre_repository=GenreRepository(db))


def _override_db(engine):
    def override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override


def test_listagem_completa_pagina_filtra_e_so_traz_obras_ativas(records):
    engine, _, _ = records
    tag = uuid4().hex[:10]
    with Session(engine) as db:
        _audit(db)
        for index in range(5):
            _book(db, f"Acervo {tag} {index}")
        _book(db, f"Acervo {tag} inativa", active=False)
        db.commit()
        service = _catalog(db)

        first = service.list_all_books(page=1, page_size=2, q=tag)
        second = service.list_all_books(page=2, page_size=2, q=tag)
        third = service.list_all_books(page=3, page_size=2, q=tag)
        assert first.total == 5 and first.page == 1 and first.page_size == 2
        titles = [b.title for p in (first, second, third) for b in p.items]
        assert titles == [f"Acervo {tag} {i}" for i in range(5)]
        assert [len(p.items) for p in (first, second, third)] == [2, 2, 1]
        assert service.list_all_books(page=9, page_size=2, q=tag).items == []

        # trecho do título, sem diferenciar caixa, com espaços aparados e curinga literal
        assert service.list_all_books(page=1, page_size=12, q=f"  {tag.upper()} 3 ").total == 1
        assert service.list_all_books(page=1, page_size=12, q="%").total == 0
        assert service.list_all_books(page=1, page_size=12, q="Autora CONSULTA").total >= 5
        # mesma disponibilidade do catálogo
        offers = first.items[0].offers
        assert offers and offers[0].destination == DestinationType.DIDACTIC and offers[0].available


def test_todas_as_categorias_incluem_as_fora_de_destaque(records):
    engine, _, _ = records
    tag = uuid4().hex[:8]
    with Session(engine) as db:
        _audit(db)
        db.add_all([Genre(name=f"Cat {tag} A", slug=f"cat-{tag}-a", is_featured=True, display_order=1),
                    Genre(name=f"Cat {tag} B", slug=f"cat-{tag}-b", is_featured=False)])
        db.commit()
        service = _catalog(db)
        featured = {g.slug for g in service.list_featured_genres()}
        every = [g.name for g in service.list_all_genres()]
        assert f"cat-{tag}-a" in featured and f"cat-{tag}-b" not in featured
        assert {f"Cat {tag} A", f"Cat {tag} B"} <= set(every)
        assert every == sorted(every)


def test_api_publica_acervo_e_categorias(records):
    engine, _, _ = records
    tag = uuid4().hex[:10]
    with Session(engine) as db:
        _audit(db)
        _book(db, f"Rota {tag}")
        db.commit()
    _override_db(engine)
    try:
        http = TestClient(app)
        page = http.get(f"/api/v1/catalog/books/all?q={tag}&page=1&page_size=5")
        assert page.status_code == 200
        body = page.json()
        assert body["total"] == 1 and body["items"][0]["title"] == f"Rota {tag}"
        assert http.get("/api/v1/catalog/books/all?page=0").status_code == 422
        assert http.get("/api/v1/catalog/books/all?page_size=49").status_code == 422
        assert http.get("/api/v1/catalog/genres?all=true").status_code == 200
        assert http.get("/api/v1/catalog/books/abc").status_code == 422
    finally:
        app.dependency_overrides.clear()


# ---- Elegibilidade -------------------------------------------------------


def _check(engine, client_id):
    with Session(engine) as db:
        return ClientEligibilityService(ClientRequestRepository(db)).check(client_id)


def test_cliente_apto(records):
    engine, _, client_id = records
    result = _check(engine, client_id)
    assert result.eligible is True and result.reasons == []


CODES = {"inactive_profile": "inactive", "inactive_user": "inactive",
         "penalized": "penalized", "overdue_loan": "overdue_loan"}


@pytest.mark.parametrize("motivo", list(CODES))
def test_cada_motivo_de_inelegibilidade(records, motivo):
    engine, book_id, client_id = records
    with Session(engine) as db:
        admin = _audit(db)
        if motivo == "inactive_profile":
            db.get(Profile, client_id).is_active = False
        elif motivo == "inactive_user":
            db.get(User, client_id).is_active = False
        elif motivo == "penalized":
            db.get(Client, client_id).is_penalized = True
        else:
            copy_id = db.scalar(select(Copy.id).where(
                Copy.book_id == book_id, Copy.destination == DestinationType.DIDACTIC))
            now = datetime.now(timezone.utc)
            db.add(Loan(client_id=client_id, copy_id=copy_id, employee_id=admin,
                        loan_date=now - timedelta(days=40), due_date=now - timedelta(days=10),
                        status=LoanStatus.OPEN))
        db.commit()
    result = _check(engine, client_id)
    assert result.eligible is False
    assert [r.code for r in result.reasons] == [CODES[motivo]]
    assert all(r.message for r in result.reasons)
    # somente leitura: a consulta não cria penalidade a partir do atraso
    with Session(engine) as db:
        assert db.get(Client, client_id).is_penalized is (motivo == "penalized")


def test_motivos_acumulam(records):
    engine, _, client_id = records
    with Session(engine) as db:
        _audit(db)
        db.get(Client, client_id).is_penalized = True
        db.get(User, client_id).is_active = False
        db.commit()
    assert [r.code for r in _check(engine, client_id).reasons] == ["inactive", "penalized"]


def test_rota_exige_sessao_e_papel_user_e_le_o_proprio_cliente(records):
    engine, _, client_id = records
    _override_db(engine)
    try:
        http = TestClient(app)
        assert http.get("/api/v1/me/eligibility").status_code == 401
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=client_id, role_codes=["SELLER"])
        assert http.get("/api/v1/me/eligibility").status_code == 403
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=client_id, role_codes=["USER"])
        response = http.get(f"/api/v1/me/eligibility?client_id={client_id + 1}")
        assert response.status_code == 200
        assert response.json() == {"eligible": True, "reasons": []}
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=client_id + 10**6, role_codes=["USER"])
        denied = http.get("/api/v1/me/eligibility")
        assert denied.status_code == 403 and denied.json()["code"] == "client_required"
    finally:
        app.dependency_overrides.clear()
