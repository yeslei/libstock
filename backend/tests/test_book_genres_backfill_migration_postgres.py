"""Migration 20261004_0017 (Issue #174): associa obras ao catálogo pelo texto `genre`, com ciclo reversível.

Usa o banco temporário de test_reservation_migrations_postgres (Alembic real, subprocesso)."""
from sqlalchemy import text
from sqlalchemy.orm import Session

from uuid import uuid4

from app.models.domain import Book, Copy, DestinationType
from test_reservation_migrations_postgres import make_user, scratch_database  # noqa: F401  (fixture)

PREVIOUS = '20261003_0016'
REVISION = '20261004_0017'


def links(engine):
    with engine.connect() as conn:
        rows = conn.execute(text(
            'SELECT bg.book_id, g.name FROM book_genres bg JOIN genres g ON g.id = bg.genre_id ORDER BY 1, 2'))
        result = {}
        for book_id, name in rows:
            result.setdefault(book_id, set()).add(name)
        return result


def seed_books(engine):
    """Devolve {chave: id}. Categorias da seed: Ficção, Não ficção, Romance, Fantasia, Suspense, Infantil, Biografia."""
    texts = {
        'exact': 'Fantasia', 'accent_case': 'FICCAO', 'multiple': 'Romance; Suspense, nao ficcao  ',
        'unmatched': 'Culinária', 'partial': 'Ficção, Culinária', 'empty': '   ', 'null': None,
        'already_linked': 'Fantasia',
        # Textos literais encontrados em produção (homologação de 2026-10-04).
        'juvenile': 'Juvenile Fiction', 'brazil': 'Brazil', 'ministracao': 'Ministração',
        'prod_multi': 'Ficção, Romance', 'prod_nf': 'Não ficção', 'slash': 'Fiction / Fantasy',
    }
    ids = {}
    with Session(engine) as db:
        admin_id = make_user(db, 'ADMINISTRATOR', 'Admin')
        db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(admin_id)})
        for key, genre in texts.items():
            book = Book(title=f'Livro {key}', author='Autor', genre=genre)
            db.add(book); db.flush()
            db.add(Copy(book_id=book.id, barcode=uuid4().hex, destination=DestinationType.DIDACTIC))
            ids[key] = book.id
        db.execute(text("INSERT INTO book_genres (book_id, genre_id) SELECT :b, id FROM genres WHERE name = 'Infantil'"),
                   {'b': ids['already_linked']})
        db.commit()
    return ids


def test_backfill_matches_by_name_ignoring_case_and_accents_and_respects_existing_links(scratch_database):  # noqa: F811
    engine, alembic = scratch_database
    alembic('upgrade', PREVIOUS)
    ids = seed_books(engine)
    assert links(engine) == {ids['already_linked']: {'Infantil'}}

    alembic('upgrade', REVISION)
    assert links(engine) == {
        ids['exact']: {'Fantasia'},
        ids['accent_case']: {'Ficção'},
        ids['multiple']: {'Romance', 'Suspense', 'Não ficção'},
        ids['partial']: {'Ficção'},  # parte sem correspondência é ignorada
        ids['already_linked']: {'Infantil'},  # obra que já tinha vínculo não é alterada
        ids['prod_multi']: {'Ficção', 'Romance'},
        ids['prod_nf']: {'Não ficção'},
    }
    # Sem categoria equivalente no catálogo; a barra não separa categorias.
    for key in ('unmatched', 'empty', 'null', 'juvenile', 'brazil', 'ministracao', 'slash'):
        assert ids[key] not in links(engine)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM audit_logs WHERE entity_type = 'book_genres' "
                                "AND new_value->>'source' = 'migration_20261004_0017'")) == 9
        # O texto original nunca é alterado.
        assert conn.scalar(text('SELECT genre FROM books WHERE id = :id'), {'id': ids['accent_case']}) == 'FICCAO'


def test_downgrade_removes_only_links_created_by_the_migration_and_cycle_is_repeatable(scratch_database):  # noqa: F811
    engine, alembic = scratch_database
    alembic('upgrade', PREVIOUS)
    ids = seed_books(engine)
    alembic('upgrade', REVISION)
    # Vínculo criado depois da migração (como faria a API) para uma obra que a migração ignorou.
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO book_genres (book_id, genre_id) SELECT :b, id FROM genres WHERE name = 'Biografia'"),
                     {'b': ids['unmatched']})

    alembic('downgrade', '-1')
    assert links(engine) == {ids['already_linked']: {'Infantil'}, ids['unmatched']: {'Biografia'}}
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM audit_logs WHERE entity_type = 'book_genres' "
                                "AND operation = 'DELETE'")) == 9

    alembic('upgrade', 'head')
    assert ids['exact'] in links(engine) and links(engine)[ids['multiple']] == {'Romance', 'Suspense', 'Não ficção'}
    assert links(engine)[ids['unmatched']] == {'Biografia'}
    alembic('downgrade', '-1')  # segundo ciclo: não duplica nem remove o que não é da migração
    assert links(engine) == {ids['already_linked']: {'Infantil'}, ids['unmatched']: {'Biografia'}}
    alembic('upgrade', 'head')
    alembic('check')
    alembic('heads')
