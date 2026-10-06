"""Associa às categorias do catálogo as obras que só têm o texto `genre` (Issue #174).

O cadastro de obra gravava apenas o texto `books.genre`, enquanto o catálogo público (páginas de categoria, filtro e
detalhe) lê `book_genres`. Para cada obra SEM nenhuma linha em `book_genres` e com `genre` preenchido, associa as
categorias de `genres` cujo nome coincide com o texto, sem diferenciar maiúsculas e acentos. O texto pode listar várias
categorias separadas por vírgula ou ponto e vírgula. Texto sem correspondência não cria nada; obra que já tem
`book_genres` não é alterada.

Rastreabilidade: cada associação criada aqui grava uma linha em `audit_logs` (entity_type `book_genres`, operação
INSERT, `new_value.source` = `migration_20261004_0017`). O downgrade remove SOMENTE essas associações (e registra uma
linha DELETE por associação removida, pois `audit_logs` é imutável). Associações criadas depois pela API, de outros
pares obra/categoria, nunca são tocadas. Limite conhecido: se uma associação desta migração tiver sido removida e
recriada manualmente depois, o downgrade a remove também (o par é o mesmo).
"""
import re
import unicodedata

import sqlalchemy as sa
from alembic import op

revision = '20261004_0017'
down_revision = '20261003_0016'
branch_labels = None
depends_on = None

SOURCE = 'migration_20261004_0017'
SEPARATORS = re.compile(r'[,;]')


def normalize(value: str) -> str:
    """Minúsculas, sem acentos e com espaços colapsados: 'Ficção  Científica' == 'ficcao cientifica'."""
    decomposed = unicodedata.normalize('NFKD', value)
    without_marks = ''.join(char for char in decomposed if not unicodedata.combining(char))
    return ' '.join(without_marks.casefold().split())


def match_genre_ids(text: str, genres_by_name: dict[str, int]) -> list[int]:
    """Ids das categorias citadas no texto: primeiro o texto inteiro; senão cada item separado por , ou ;."""
    whole = genres_by_name.get(normalize(text))
    if whole is not None:
        return [whole]
    found: list[int] = []
    for part in SEPARATORS.split(text):
        genre_id = genres_by_name.get(normalize(part))
        if genre_id is not None and genre_id not in found:
            found.append(genre_id)
    return found


def upgrade():
    connection = op.get_bind()
    genres_by_name: dict[str, int] = {}
    # Ordem por id: se dois nomes colidirem após a normalização, vale a categoria mais antiga.
    for genre_id, name in connection.execute(sa.text('SELECT id, name FROM genres ORDER BY id')):
        genres_by_name.setdefault(normalize(name), genre_id)
    if not genres_by_name:
        return

    books = connection.execute(sa.text("""
        SELECT b.id, b.genre FROM books b
        WHERE b.genre IS NOT NULL AND btrim(b.genre) <> ''
          AND NOT EXISTS (SELECT 1 FROM book_genres bg WHERE bg.book_id = b.id)
        ORDER BY b.id
    """)).all()
    insert_link = sa.text('INSERT INTO book_genres (book_id, genre_id) VALUES (:book_id, :genre_id)')
    insert_audit = sa.text("""
        INSERT INTO audit_logs (entity_type, entity_id, operation, new_value)
        VALUES ('book_genres', :entity_id, 'INSERT', CAST(:new_value AS jsonb))
    """)
    for book_id, text in books:
        for genre_id in match_genre_ids(text, genres_by_name):
            connection.execute(insert_link, {'book_id': book_id, 'genre_id': genre_id})
            connection.execute(insert_audit, {
                'entity_id': f'{book_id}:{genre_id}',
                'new_value': f'{{"book_id": {book_id}, "genre_id": {genre_id}, "source": "{SOURCE}"}}',
            })


def downgrade():
    connection = op.get_bind()
    # Associações inseridas por esta migração e ainda não desfeitas por um downgrade anterior.
    created = connection.execute(sa.text("""
        SELECT i.entity_id, (i.new_value->>'book_id')::bigint, (i.new_value->>'genre_id')::bigint
        FROM audit_logs i
        WHERE i.entity_type = 'book_genres' AND i.operation = 'INSERT' AND i.new_value->>'source' = :source
          AND NOT EXISTS (
              SELECT 1 FROM audit_logs d
              WHERE d.entity_type = 'book_genres' AND d.operation = 'DELETE'
                AND d.entity_id = i.entity_id AND d.old_value->>'source' = :source AND d.id > i.id)
        ORDER BY i.id
    """), {'source': SOURCE}).all()
    for entity_id, book_id, genre_id in created:
        removed = connection.execute(
            sa.text('DELETE FROM book_genres WHERE book_id = :book_id AND genre_id = :genre_id'),
            {'book_id': book_id, 'genre_id': genre_id},
        ).rowcount
        if removed:
            connection.execute(sa.text("""
                INSERT INTO audit_logs (entity_type, entity_id, operation, old_value)
                VALUES ('book_genres', :entity_id, 'DELETE', CAST(:old_value AS jsonb))
            """), {
                'entity_id': entity_id,
                'old_value': f'{{"book_id": {book_id}, "genre_id": {genre_id}, "source": "{SOURCE}"}}',
            })
