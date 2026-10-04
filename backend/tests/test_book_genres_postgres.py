"""Categorias da obra no cadastro/edição (Issue #174) e dados informados vs Google Books (Issue #176),
contra PostgreSQL descartável migrado pelo Alembic. O Google Books é sempre simulado."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.dependencies.authentication import get_current_user
from app.dependencies.services import get_book_service, get_catalog_service
from app.main import app
from app.repositories.book_repository import BookRepository
from app.repositories.catalog_repository import CatalogRepository, GenreRepository
from app.schemas.book_schema import BookUpdate
from app.services.book_service import BookService
from app.services.catalog_service import CatalogService
from test_acervo_seller_postgres import acervo  # noqa: F401  (fixture)
from test_client_requests_postgres import records  # noqa: F401  (fixture)
from test_staff_desk_postgres import desk  # noqa: F401  (fixtures)

EXTERNAL = {
    'title': 'Título do Google',
    'author': 'Augusto Cury, Editora Saraiva',
    'genre': 'Juvenile Fiction',
    'cover_url': 'https://books.example/capa.jpg',
    'publisher': 'Saraiva',
    'publication_year': '2015',
}


def isbn13() -> str:
    body = '978' + ''.join(str(int(c, 16) % 10) for c in uuid4().hex[:9])
    check = (10 - sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(body)) % 10) % 10
    return body + str(check)


@pytest.fixture
def genres_env(acervo):  # noqa: F811
    sessions = []

    def session():
        db = Session(acervo.engine)
        sessions.append(db)
        return db

    def book_service():
        db = session()
        service = BookService(db=db, repository=BookRepository(db))
        service.fetch_google_books_data = AsyncMock(return_value=dict(EXTERNAL))
        return service

    app.dependency_overrides[get_book_service] = book_service
    app.dependency_overrides[get_catalog_service] = lambda: CatalogService(
        db=(db := session()), catalog_repository=CatalogRepository(db), genre_repository=GenreRepository(db))
    with Session(acervo.engine) as db:
        ids = {name: gid for gid, name in db.execute(text('SELECT id, name FROM genres'))}
    yield NS(acervo=acervo, http=acervo.http, engine=acervo.engine, ids=ids, book_service=book_service)
    for db in sessions:
        db.close()


def create_payload(**extra):
    payload = {'isbn': isbn13(), 'title': 'Obra do funcionário', 'author': 'Autor do funcionário',
               'initial_copy': {'barcode': 'GEN-' + uuid4().hex[:12], 'destination': 'DIDACTIC'}}
    payload.update(extra)
    return payload


def links(engine, book_id):
    with engine.connect() as conn:
        return {name for (name,) in conn.execute(text(
            'SELECT g.name FROM book_genres bg JOIN genres g ON g.id = bg.genre_id WHERE bg.book_id = :id'),
            {'id': book_id})}


def book_row(engine, book_id):
    with engine.connect() as conn:
        return conn.execute(text('SELECT title, author, genre, cover_url, publisher, publication_year FROM books WHERE id = :id'),
                            {'id': book_id}).one()


def audit_count(engine, book_id, operation):
    with engine.connect() as conn:
        return conn.scalar(text("SELECT count(*) FROM audit_logs WHERE entity_type = 'books' AND entity_id = :id "
                                'AND operation = :op'), {'id': str(book_id), 'op': operation})


def test_create_with_genre_ids_syncs_links_text_and_public_catalog(genres_env):
    env = genres_env
    ids = [env.ids['Romance'], env.ids['Fantasia']]
    response = env.http.post('/api/v1/books/', json=create_payload(genre_ids=ids))
    assert response.status_code == 201, response.text
    body = response.json()
    assert [g['name'] for g in body['genres']] == ['Fantasia', 'Romance']
    assert body['genre'] == 'Romance, Fantasia'  # texto legado espelha a seleção, na ordem informada
    assert links(env.engine, body['id']) == {'Romance', 'Fantasia'}
    assert audit_count(env.engine, body['id'], 'INSERT') == 1  # auditoria da obra como no resto do acervo
    # Catálogo público: página da categoria e detalhe.
    page = env.http.get('/api/v1/catalog/genres/fantasia/books', params={'page_size': 48}).json()
    assert body['id'] in [item['id'] for item in page['items']]
    detail = env.http.get(f"/api/v1/catalog/books/{body['id']}").json()
    assert sorted(detail['genres']) == ['Fantasia', 'Romance']
    # Detalhe do balcão e lista do balcão exibem as categorias do catálogo.
    staff = env.http.get(f"/api/v1/staff/books/{body['id']}").json()
    assert [g['name'] for g in staff['genres']] == ['Fantasia', 'Romance']
    listed = env.http.get('/api/v1/staff/books', params={'q': 'Obra do funcionário', 'limit': 100}).json()
    assert [g['slug'] for g in next(b for b in listed if b['id'] == body['id'])['genres']] == ['fantasia', 'romance']


def test_google_books_never_overrides_informed_data_or_defines_genres(genres_env):
    """Issue #176 sobre PostgreSQL: título, autor e categorias digitados prevalecem; o externo só preenche vazios."""
    env = genres_env
    response = env.http.post('/api/v1/books/', json=create_payload(genre_ids=[env.ids['Infantil']]))
    assert response.status_code == 201, response.text
    book_id = response.json()['id']
    row = book_row(env.engine, book_id)
    assert (row.title, row.author, row.genre) == ('Obra do funcionário', 'Autor do funcionário', 'Infantil')
    assert (row.cover_url, row.publisher, row.publication_year) == ('https://books.example/capa.jpg', 'Saraiva', 2015)
    assert links(env.engine, book_id) == {'Infantil'}  # "Juvenile Fiction" jamais vira categoria

    only_isbn = env.http.post('/api/v1/books/', json={
        'isbn': isbn13(), 'initial_copy': {'barcode': 'GEN-' + uuid4().hex[:12], 'destination': 'DIDACTIC'}})
    assert only_isbn.status_code == 201, only_isbn.text
    filled = book_row(env.engine, only_isbn.json()['id'])
    assert (filled.title, filled.author) == ('Título do Google', 'Augusto Cury, Editora Saraiva')
    assert filled.genre is None and links(env.engine, only_isbn.json()['id']) == set()  # externo preenche vazios, não categoria


def test_create_without_genre_ids_keeps_legacy_text_and_creates_no_links(genres_env):
    env = genres_env
    response = env.http.post('/api/v1/books/', json=create_payload(genre='Texto livre'))
    assert response.status_code == 201
    assert response.json()['genre'] == 'Texto livre' and response.json()['genres'] == []
    assert links(env.engine, response.json()['id']) == set()


def test_unknown_genre_id_is_404_and_nothing_is_persisted(genres_env):
    env = genres_env
    payload = create_payload(genre_ids=[env.ids['Romance'], 99999])
    response = env.http.post('/api/v1/books/', json=payload)
    assert response.status_code == 404
    assert response.json() == {'detail': 'Gênero não encontrado.', 'code': 'genre_not_found',
                               'details': {'missing_ids': [99999]}}
    with env.engine.connect() as conn:
        assert conn.scalar(text('SELECT count(*) FROM books WHERE isbn = :i'), {'i': payload['isbn']}) == 0
        assert conn.scalar(text('SELECT count(*) FROM copies WHERE barcode = :b'),
                           {'b': payload['initial_copy']['barcode']}) == 0


@pytest.mark.parametrize('genre_ids', [[0], [-3], ['x'], [1.5], 'Romance', list(range(1, 22))])
def test_malformed_genre_ids_are_422(genres_env, genre_ids):
    response = genres_env.http.post('/api/v1/books/', json=create_payload(genre_ids=genre_ids))
    assert response.status_code == 422


def test_duplicate_genre_ids_are_deduplicated(genres_env):
    env = genres_env
    romance = env.ids['Romance']
    response = env.http.post('/api/v1/books/', json=create_payload(genre_ids=[romance, romance]))
    assert response.status_code == 201
    assert [g['name'] for g in response.json()['genres']] == ['Romance']


def test_patch_replaces_and_clears_genres_and_audits(genres_env):
    env = genres_env
    book_id = env.acervo.book_id
    before = audit_count(env.engine, book_id, 'UPDATE')
    only_genres = env.http.patch(f'/api/v1/books/{book_id}', json={'genre_ids': [env.ids['Suspense']]})
    assert only_genres.status_code == 200, only_genres.text
    assert [g['name'] for g in only_genres.json()['genres']] == ['Suspense']
    assert only_genres.json()['genre'] == 'Suspense'
    assert links(env.engine, book_id) == {'Suspense'}
    # Mudança só de categorias também é auditada na obra, com o funcionário responsável.
    assert audit_count(env.engine, book_id, 'UPDATE') == before + 1
    with env.engine.connect() as conn:
        assert conn.scalar(text("SELECT employee_id FROM audit_logs WHERE entity_type = 'books' AND entity_id = :id "
                                'AND operation = :op ORDER BY id DESC LIMIT 1'),
                           {'id': str(book_id), 'op': 'UPDATE'}) == env.acervo.seller_id

    two = env.http.patch(f'/api/v1/books/{book_id}', json={'genre_ids': [env.ids['Romance'], env.ids['Biografia']],
                                                           'title': 'Novo título'})
    assert two.status_code == 200 and two.json()['title'] == 'Novo título'
    assert links(env.engine, book_id) == {'Romance', 'Biografia'}

    same = env.http.patch(f'/api/v1/books/{book_id}', json={'genre_ids': [env.ids['Biografia'], env.ids['Romance']]})
    assert same.status_code == 200 and links(env.engine, book_id) == {'Romance', 'Biografia'}

    cleared = env.http.patch(f'/api/v1/books/{book_id}', json={'genre_ids': []})
    assert cleared.status_code == 200
    assert cleared.json()['genres'] == [] and cleared.json()['genre'] is None
    assert links(env.engine, book_id) == set()


def test_patch_with_text_only_does_not_touch_associations(genres_env):
    env = genres_env
    book_id = env.acervo.book_id
    assert env.http.patch(f'/api/v1/books/{book_id}', json={'genre_ids': [env.ids['Romance']]}).status_code == 200
    response = env.http.patch(f'/api/v1/books/{book_id}', json={'genre': 'Outro texto'})
    assert response.status_code == 200 and response.json()['genre'] == 'Outro texto'
    assert links(env.engine, book_id) == {'Romance'}


def test_patch_invalid_genres_keeps_previous_state(genres_env):
    env = genres_env
    book_id = env.acervo.book_id
    assert env.http.patch(f'/api/v1/books/{book_id}', json={'genre_ids': [env.ids['Romance']]}).status_code == 200
    missing = env.http.patch(f'/api/v1/books/{book_id}', json={'title': 'Não deve gravar', 'genre_ids': [123456]})
    assert missing.status_code == 404 and missing.json()['code'] == 'genre_not_found'
    assert env.http.patch(f'/api/v1/books/{book_id}', json={'genre_ids': None}).status_code == 422
    assert env.http.patch(f'/api/v1/books/{book_id}', json={'genre_ids': [0]}).status_code == 422
    assert links(env.engine, book_id) == {'Romance'}
    assert book_row(env.engine, book_id).title != 'Não deve gravar'
    assert env.http.patch('/api/v1/books/99999999', json={'genre_ids': [env.ids['Romance']]}).status_code == 404


def test_patch_genres_roles(genres_env):
    env = genres_env
    book_id = env.acervo.book_id
    env.acervo.state.roles = ['USER']
    assert env.http.patch(f'/api/v1/books/{book_id}', json={'genre_ids': [env.ids['Romance']]}).status_code == 403
    assert env.http.post('/api/v1/books/', json=create_payload(genre_ids=[env.ids['Romance']])).status_code == 403
    env.acervo.state.roles = ['STOCK_KEEPER']
    assert env.http.patch(f'/api/v1/books/{book_id}', json={'genre_ids': [env.ids['Romance']]}).status_code == 200
    app.dependency_overrides.pop(get_current_user, None)
    assert env.http.patch(f'/api/v1/books/{book_id}', json={'genre_ids': [env.ids['Romance']]}).status_code == 401


def test_concurrent_genre_updates_of_the_same_book_never_fail(genres_env):
    env = genres_env
    book_id = env.acervo.book_id
    wanted = [env.ids['Romance'], env.ids['Fantasia']]

    def update(_):
        with Session(env.engine) as db:
            service = BookService(db=db, repository=BookRepository(db))
            service.update_book(book_id, BookUpdate(genre_ids=wanted), employee_id=env.acervo.seller_id)
            return True

    with ThreadPoolExecutor(max_workers=6) as pool:
        assert all(pool.map(update, range(6)))
    assert links(env.engine, book_id) == {'Romance', 'Fantasia'}



def test_genre_text_together_with_genre_ids_is_422_and_persists_nothing(genres_env):
    env = genres_env
    book_id = env.acervo.book_id
    payload = create_payload(genre='Texto', genre_ids=[env.ids['Romance']])
    response = env.http.post('/api/v1/books/', json=payload)
    assert (response.status_code, response.json()['code']) == (422, 'genre_text_with_genre_ids')
    with env.engine.connect() as conn:
        assert conn.scalar(text('SELECT count(*) FROM books WHERE isbn = :i'), {'i': payload['isbn']}) == 0
    patch = env.http.patch(f'/api/v1/books/{book_id}', json={'genre': 'Texto', 'genre_ids': [env.ids['Romance']]})
    assert (patch.status_code, patch.json()['code']) == (422, 'genre_text_with_genre_ids')
    assert links(env.engine, book_id) == set()


def test_genre_removed_concurrently_is_404_never_500(genres_env):
    """A categoria removida por outra transação (ainda não confirmada) é esperada pelo FOR SHARE: 404."""
    import threading
    import time
    from app.core.exceptions import GenreNotFoundError
    env = genres_env
    book_id = env.acervo.book_id
    with Session(env.engine) as db:
        db.execute(text("INSERT INTO genres (name, slug) VALUES ('Efêmera', 'efemera')"))
        db.commit()
        gid = db.scalar(text("SELECT id FROM genres WHERE slug = 'efemera'"))
    deleter = Session(env.engine)
    deleter.execute(text('DELETE FROM genres WHERE id = :id'), {'id': gid})  # sem commit
    outcome = {}

    def patch():
        with Session(env.engine) as db:
            try:
                BookService(db=db, repository=BookRepository(db)).update_book(
                    book_id, BookUpdate(genre_ids=[gid]), employee_id=env.acervo.seller_id)
                outcome['result'] = 'ok'
            except GenreNotFoundError as error:
                outcome['result'] = (error.status_code, error.code)

    thread = threading.Thread(target=patch)
    thread.start()
    time.sleep(0.8)
    assert thread.is_alive()  # espera atrás da exclusão pendente (FOR SHARE)
    deleter.commit()
    deleter.close()
    thread.join(10)
    assert outcome['result'] == (404, 'genre_not_found')
    assert links(env.engine, book_id) == set()


def test_api_genre_changes_are_audited_with_the_employee_and_not_tagged_as_migration(genres_env):
    env = genres_env
    book_id = env.acervo.book_id
    r, f = env.ids['Romance'], env.ids['Fantasia']
    assert env.http.patch(f'/api/v1/books/{book_id}', json={'genre_ids': [r]}).status_code == 200
    assert env.http.patch(f'/api/v1/books/{book_id}', json={'genre_ids': [f]}).status_code == 200
    with env.engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT operation, entity_id, employee_id, coalesce(new_value, old_value) AS value FROM audit_logs "
            "WHERE entity_type = 'book_genres' AND entity_id LIKE :p ORDER BY id"), {'p': f'{book_id}:%'}).all()
    assert [(row.operation, row.entity_id) for row in rows] == [
        ('INSERT', f'{book_id}:{r}'), ('DELETE', f'{book_id}:{r}'), ('INSERT', f'{book_id}:{f}')]
    assert {row.employee_id for row in rows} == {env.acervo.seller_id}
    assert all(row.value == {'book_id': book_id, 'genre_id': int(row.entity_id.split(':')[1])} for row in rows)
    assert all('source' not in row.value for row in rows)  # a migration 0017 só desfaz linhas com `source`

    created = env.http.post('/api/v1/books/', json=create_payload(genre_ids=[r, f])).json()
    with env.engine.connect() as conn:
        count = conn.scalar(text("SELECT count(*) FROM audit_logs WHERE entity_type = 'book_genres' "
                                 "AND operation = 'INSERT' AND entity_id LIKE :p AND employee_id = :e"),
                            {'p': f"{created['id']}:%", 'e': env.acervo.seller_id})
    assert count == 2
