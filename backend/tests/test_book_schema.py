import unittest
from types import SimpleNamespace

from pydantic import ValidationError

from app.schemas.book_schema import BookResponse, BookSearchParams


class BookSearchParamsTests(unittest.TestCase):
    def test_trims_title_without_collapsing_internal_whitespace(self) -> None:
        params = BookSearchParams(title="  O   Hobbit  ")

        self.assertEqual(params.title, "O   Hobbit")

    def test_rejects_blank_title(self) -> None:
        with self.assertRaises(ValidationError):
            BookSearchParams(title="   ")

    def test_does_not_restrict_search_term_to_database_column_length(self) -> None:
        params = BookSearchParams(title="a" * 256)

        self.assertEqual(params.title, "a" * 256)


class BookResponseTests(unittest.TestCase):
    def test_serializes_from_book_attributes(self) -> None:
        book = SimpleNamespace(
            id=1,
            title="O Hobbit",
            author="J. R. R. Tolkien",
            is_active=True,
        )

        response = BookResponse.model_validate(book)

        self.assertEqual(
            response.model_dump(),
            {
                "id": 1,
                "title": "O Hobbit",
                "author": "J. R. R. Tolkien",
                "is_active": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
