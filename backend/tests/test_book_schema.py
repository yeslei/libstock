import unittest
from types import SimpleNamespace

from pydantic import ValidationError

from app.schemas.book_schema import BookCreate, BookResponse, BookSearchParams, BookUpdate


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
            isbn=None,
            genre=None,
        )

        response = BookResponse.model_validate(book)

        self.assertEqual(
            response.model_dump(),
            {
                "id": 1,
                "isbn": None,
                "title": "O Hobbit",
                "author": "J. R. R. Tolkien",
                "genre": None,
                "cover_url": None,
                "is_active": True,
                "initial_copy": None,
            },
        )

    def test_accepts_valid_book_payload(self) -> None:
        book = BookCreate.model_validate(
            {
                "isbn": "9788575225530",
                "title": "Python Fluente",
                "author": "Luciano Ramalho",
                "initial_copy": {
                    "barcode": "EX-1",
                    "destination": "DIDACTIC",
                },
            }
        )

        self.assertEqual(book.isbn, "9788575225530")

    def test_rejects_state_fields_at_book_root(self) -> None:
        for field, value in (("status", "INACTIVE"), ("is_active", True)):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                BookCreate.model_validate(
                    {
                        "isbn": "9788575225530",
                        "initial_copy": {
                            "barcode": "EX-1",
                            "destination": "DIDACTIC",
                        },
                        field: value,
                    }
                )

    def test_book_create_openapi_forbids_additional_properties(self) -> None:
        schema = BookCreate.model_json_schema()

        self.assertFalse(schema["additionalProperties"])

    def test_commercial_initial_copy_requires_price(self) -> None:
        with self.assertRaises(ValidationError):
            BookCreate.model_validate(
                {
                    "isbn": "9788575225530",
                    "title": "Python Fluente",
                    "author": "Luciano Ramalho",
                    "initial_copy": {
                        "barcode": "COM-1",
                        "destination": "COMMERCIAL",
                    },
                }
            )

    def test_initial_copy_rejects_state_fields_from_request(self) -> None:
        for field, value in (("status", "INACTIVE"), ("is_active", True)):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                BookCreate.model_validate(
                    {
                        "isbn": "9788575225530",
                        "title": "Python Fluente",
                        "author": "Luciano Ramalho",
                        "initial_copy": {
                            "barcode": "EX-1",
                            "destination": "DIDACTIC",
                            field: value,
                        },
                    }
                )


class BookUpdateTests(unittest.TestCase):
    def test_accepts_valid_partial_update(self) -> None:
        update = BookUpdate.model_validate({"title": "Dom Casmurro", "publication_year": 1899})
        self.assertEqual(update.title, "Dom Casmurro")
        self.assertEqual(update.publication_year, 1899)
        self.assertIsNone(update.author)
        self.assertIsNone(update.isbn)

    def test_validates_and_normalizes_isbn(self) -> None:
        update = BookUpdate.model_validate({"isbn": "978-85-7522-553-0"})
        self.assertEqual(update.isbn, "9788575225530")

    def test_rejects_invalid_isbn(self) -> None:
        with self.assertRaises(ValidationError):
            BookUpdate.model_validate({"isbn": "12345"})

    def test_rejects_blank_mandatory_fields(self) -> None:
        for field in ("title", "author"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                BookUpdate.model_validate({field: "   "})

    def test_rejects_year_outside_valid_range(self) -> None:
        for year in (999, 2101):
            with self.subTest(year=year), self.assertRaises(ValidationError):
                BookUpdate.model_validate({"publication_year": year})

    def test_forbids_extra_fields(self) -> None:
        with self.assertRaises(ValidationError):
            BookUpdate.model_validate({"extra_field": "not_allowed"})


if __name__ == "__main__":
    unittest.main()
