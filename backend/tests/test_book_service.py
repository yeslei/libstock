import unittest
from unittest.mock import Mock

from app.services.book_service import BookService


class BookServiceTests(unittest.TestCase):
    def test_search_trims_title_without_collapsing_internal_whitespace(self) -> None:
        repository = Mock()
        repository.search_by_title.return_value = []
        service = BookService(repository)

        self.assertEqual(service.search_books("  O   Hobbit  "), [])
        repository.search_by_title.assert_called_once_with("O   Hobbit")

    def test_search_rejects_blank_title(self) -> None:
        repository = Mock()
        service = BookService(repository)

        with self.assertRaises(ValueError):
            service.search_books("   ")
        repository.search_by_title.assert_not_called()
