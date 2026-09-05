from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.domain import Book, BookGenre, Copy, CopyStatus, Genre


class CatalogRepository:
    """Leitura do catálogo público.

    Só devolve livros ativos que tenham ao menos um exemplar disponível — um
    livro sem exemplar disponível não tem o que oferecer na vitrine.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def _available_books(self) -> Select[tuple[Book]]:
        has_available_copy = (
            select(Copy.id)
            .where(
                Copy.book_id == Book.id,
                Copy.is_active.is_(True),
                Copy.status == CopyStatus.AVAILABLE,
            )
            .exists()
        )
        return (
            select(Book)
            .options(
                selectinload(Book.genres).selectinload(BookGenre.genre),
                selectinload(Book.copies),
            )
            .where(Book.is_active.is_(True), has_available_copy)
        )

    def find_featured_books(self, *, limit: int) -> list[Book]:
        statement = (
            self._available_books()
            .where(Book.is_featured.is_(True))
            # NULLS LAST: um destaque sem posição definida vai para o fim em
            # vez de encabeçar a vitrine, que é o que o Postgres faria por
            # padrão na ordenação ascendente.
            .order_by(Book.featured_position.asc().nulls_last(), Book.title.asc())
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    def find_books_by_genre(
        self,
        *,
        genre_id: int,
        page: int,
        page_size: int,
    ) -> tuple[list[Book], int]:
        filtered = self._available_books().where(
            select(BookGenre.book_id)
            .where(BookGenre.book_id == Book.id, BookGenre.genre_id == genre_id)
            .exists()
        )

        total = self.db.scalar(
            select(func.count()).select_from(filtered.order_by(None).subquery())
        )
        items = list(
            self.db.scalars(
                filtered.order_by(Book.title.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total or 0

    def find_book_by_id(self, book_id: int) -> Book | None:
        statement = (
            select(Book)
            .options(selectinload(Book.genres).selectinload(BookGenre.genre))
            .where(Book.id == book_id)
        )
        return self.db.scalar(statement)


class GenreRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_featured(self) -> list[Genre]:
        statement = (
            select(Genre)
            .where(Genre.is_featured.is_(True))
            .order_by(Genre.display_order.asc().nulls_last(), Genre.name.asc())
        )
        return list(self.db.scalars(statement))

    def find_by_slug(self, slug: str) -> Genre | None:
        return self.db.scalar(select(Genre).where(Genre.slug == slug))

    def find_by_id(self, genre_id: int) -> Genre | None:
        return self.db.scalar(select(Genre).where(Genre.id == genre_id))

    def exists_with_name_or_slug(self, *, name: str, slug: str) -> bool:
        statement = select(Genre.id).where(
            (func.lower(Genre.name) == name.lower()) | (Genre.slug == slug)
        )
        return self.db.scalar(statement) is not None

    def create(self, *, name: str, slug: str, is_featured: bool, display_order: int | None) -> Genre:
        genre = Genre(
            name=name,
            slug=slug,
            is_featured=is_featured,
            display_order=display_order,
        )
        self.db.add(genre)
        self.db.flush()
        self.db.refresh(genre)
        return genre
