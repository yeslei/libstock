import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.domain import Book
from app.repositories.book_repository import BookRepository


class BookRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Book.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.db.add_all(
            [
                Book(id=1, title="Dom Casmurro", author="Machado", is_active=True),
                Book(id=2, title="O HOBBIT", author="Tolkien", is_active=True),
                Book(id=3, title="Hobbit inativo", author="Tolkien", is_active=False),
                Book(id=4, title="Desconto 10%", author="Autor", is_active=True),
                Book(id=5, title="Código_Azul", author="Autor", is_active=True),
                Book(id=6, title="Desconto 100", author="Autor", is_active=True),
                Book(id=7, title="CódigoXAzul", author="Autor", is_active=True),
            ]
        )
        self.db.commit()
        self.repository = BookRepository(self.db)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_search_is_case_insensitive(self) -> None:
        self.assertEqual(
            [book.title for book in self.repository.search_by_title("hobbit")],
            ["O HOBBIT"],
        )

    def test_search_matches_title_substring(self) -> None:
        self.assertEqual(
            [book.title for book in self.repository.search_by_title("cas")],
            ["Dom Casmurro"],
        )

    def test_search_returns_only_active_books(self) -> None:
        self.assertEqual(
            [book.title for book in self.repository.search_by_title("Hobbit")],
            ["O HOBBIT"],
        )

    def test_percent_is_matched_as_literal_text(self) -> None:
        self.assertEqual(
            [book.title for book in self.repository.search_by_title("10%")],
            ["Desconto 10%"],
        )

    def test_underscore_is_matched_as_literal_text(self) -> None:
        self.assertEqual(
            [book.title for book in self.repository.search_by_title("_")],
            ["Código_Azul"],
        )
