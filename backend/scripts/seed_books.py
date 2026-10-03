"""Acervo demonstrativo local. Execute: python -m scripts.seed_books.

As datas de empréstimo e ISBNs são fixtures, não políticas da biblioteca nem
identificadores das edições reais. Não altera registros já existentes.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.models.domain import (
    Book, BookGenre, Client, Copy, CopyStatus, DestinationType, Employee,
    Genre, Loan, LoanStatus, Profile,
)
from app.models.user import User
from scripts.seed_users import seed_users

# Prefixos de teste com checksum ISBN-13 válido.
BOOKS = (
    ("9780000000002", "Dom Casmurro", "Machado de Assis", "Romance", "romance",
     (("DIDACTIC", None, False), ("DIDACTIC", None, False), ("COMMERCIAL", "29.90", False))),
    ("9780000000019", "Sapiens", "Yuval Noah Harari", "Não ficção", "nao-ficcao",
     (("COMMERCIAL", "49.90", False),)),
    ("9780000000026", "1984", "George Orwell", "Ficção", "ficcao",
     (("DIDACTIC", None, True),)),
    ("9780000000033", "O Pequeno Príncipe", "Antoine de Saint-Exupéry", "Infantil", "infantil",
     (("COMMERCIAL", "24.90", True),)),
)


def seed_books() -> None:
    if get_settings().app_env != "development" or engine.url.host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Esta seed só pode ser executada em PostgreSQL local de desenvolvimento.")

    seed_users()
    created_books = created_copies = created_loans = 0
    with SessionLocal.begin() as db:
        # Serializa execuções desta seed; UNIQUE ainda protege ISBN e barcode.
        db.execute(text("SELECT pg_advisory_xact_lock(72638194)"))
        admin = db.scalar(select(User).where(User.email == "admin@libstock.com.br"))
        customer = db.scalar(select(User).where(User.email == "cliente@libstock.com.br"))
        if admin is None or customer is None or db.get(Employee, admin.id) is None:
            raise RuntimeError("As contas de demonstração não foram criadas corretamente.")
        if db.get(Profile, customer.id) is None:
            db.add(Profile(id=customer.id))
            db.flush()
        if db.get(Client, customer.id) is None:
            db.add(Client(id=customer.id))
            db.flush()
        db.execute(text("SELECT set_config('libstock.employee_id', :actor, true)"), {"actor": str(admin.id)})

        for position, (isbn, title, author, genre_name, slug, copies) in enumerate(BOOKS, 1):
            genre = db.scalar(select(Genre).where(Genre.slug == slug))
            if genre is None:
                genre = Genre(name=genre_name, slug=slug, is_featured=True, display_order=position)
                db.add(genre)
                db.flush()
            book = db.scalar(select(Book).where(Book.isbn == isbn))
            if book is None:
                book = Book(isbn=isbn, title=title, author=author, genre=genre_name,
                            is_active=True, is_featured=True, featured_position=position)
                db.add(book)
                db.flush()
                created_books += 1
            elif book.title != title or book.author != author:
                raise RuntimeError(f"O ISBN de teste {isbn} já pertence a outro registro.")
            if db.get(BookGenre, (book.id, genre.id)) is None:
                db.add(BookGenre(book_id=book.id, genre_id=genre.id))

            for number, (destination, price, borrowed) in enumerate(copies, 1):
                barcode = f"DEMO-{isbn}-{number:02d}"
                existing = db.scalar(select(Copy).where(Copy.barcode == barcode))
                if existing is not None:
                    if existing.book_id != book.id:
                        raise RuntimeError(f"Código de teste {barcode} já pertence a outra obra.")
                    continue
                copy = Copy(book_id=book.id, barcode=barcode, destination=DestinationType(destination),
                            status=CopyStatus.AVAILABLE, sale_price=Decimal(price) if price else None,
                            condition="Bom", is_active=True)
                db.add(copy)
                db.flush()
                created_copies += 1
                if borrowed:
                    now = datetime.now(timezone.utc)
                    # O trigger do empréstimo atualiza o exemplar e registra auditoria.
                    db.add(Loan(copy_id=copy.id, client_id=customer.id, employee_id=admin.id,
                                loan_date=now, due_date=now + timedelta(days=30), status=LoanStatus.OPEN))
                    db.flush()
                    created_loans += 1

    print(f"Seed local concluída: {created_books} obras, {created_copies} exemplares e {created_loans} empréstimos demonstrativos novos.")
    print("Registros existentes foram preservados. Os ISBNs e as datas são apenas dados de teste.")


if __name__ == "__main__":
    seed_books()
