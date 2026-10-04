"""Migrations 0014 (backfill do prazo) e 0015 (fila WAITING com exemplar livre) em banco PostgreSQL próprio.

Cria e remove um banco temporário no mesmo servidor de LIBSTOCK_V2_TEST_DATABASE_URL, migra com o Alembic real
(subprocesso, ciclo upgrade/downgrade) e nunca toca o banco da aplicação nem o banco compartilhado dos demais testes."""
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models.domain import (
    Book, Client, Copy, DestinationType, Employee, Loan, LoanStatus, Profile, PurchaseReservation, ReservationStatus, Role, UserRole,
)
from app.models.user import User

BACKEND = Path(__file__).parents[1]


@pytest.fixture
def scratch_database():
    base = os.environ.get('LIBSTOCK_V2_TEST_DATABASE_URL')
    if not base:
        pytest.skip('requires isolated migrated PostgreSQL test database')
    name = f'libstock_mig_{uuid4().hex[:12]}'
    admin = create_engine(make_url(base).set(database='postgres'), isolation_level='AUTOCOMMIT')
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE {name}'))
    url = make_url(base).set(database=name)
    engine = create_engine(url)

    def alembic(*args):
        env = {**os.environ, 'DATABASE_URL': url.render_as_string(hide_password=False)}
        result = subprocess.run([sys.executable, '-m', 'alembic', *args], cwd=BACKEND, env=env,
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
    try:
        yield engine, alembic
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)'))
        admin.dispose()


def make_user(db, role_code, name):
    role = db.scalar(select(Role).where(Role.code == role_code))
    user = User(name=name, email=f'{uuid4().hex}@test.invalid', password_hash='test')
    db.add(user); db.flush()
    db.add(Profile(id=user.id)); db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    if role_code == 'USER':
        db.add(Client(id=user.id))
    else:
        db.add(Employee(id=user.id, role_id=role.id, employee_code=uuid4().hex))
    db.flush()
    return user.id


def seed_book(db, copies=1):
    admin_id = make_user(db, 'ADMINISTRATOR', 'Admin')
    db.execute(text("SELECT set_config('libstock.employee_id', :id, true)"), {'id': str(admin_id)})
    book = Book(title='Livro migração', author='Autor')
    db.add(book); db.flush()
    db.add(Copy(book_id=book.id, barcode=uuid4().hex, destination=DestinationType.DIDACTIC))
    ids = []
    for _ in range(copies):
        copy = Copy(book_id=book.id, barcode=uuid4().hex, destination=DestinationType.COMMERCIAL, sale_price=25)
        db.add(copy); db.flush()
        ids.append(copy.id)
    return book.id, ids


def test_backfill_sets_deadline_of_notified_reservations_and_cycle_is_reversible(scratch_database):
    engine, alembic = scratch_database
    alembic('upgrade', '20261003_0013')
    notified_at = datetime(2026, 10, 4, 2, 30, tzinfo=timezone.utc)  # 23:30 de 03/10 em São Paulo
    with Session(engine) as db:
        book_id, (copy_a, copy_b, copy_c) = seed_book(db, copies=3)
        clients = [make_user(db, 'USER', f'Cliente {n}') for n in range(4)]
        ids = {}
        for key, client, copy, status, stamp, expires in (
            ('legacy', clients[0], copy_a, ReservationStatus.NOTIFIED, notified_at, None),
            ('penalized', clients[1], copy_b, ReservationStatus.NOTIFIED, notified_at, None),
            ('has_deadline', clients[2], copy_c, ReservationStatus.NOTIFIED, notified_at,
             datetime(2030, 1, 1, tzinfo=timezone.utc)),
        ):
            reservation = PurchaseReservation(book_id=book_id, client_id=client, status=status, allocated_copy_id=copy,
                                              notified_at=stamp, requested_at=stamp.replace(day=3), expires_at=expires)
            db.add(reservation); db.flush()
            ids[key] = reservation.id
        waiting = PurchaseReservation(book_id=book_id, client_id=clients[3], status=ReservationStatus.WAITING)
        db.add(waiting); db.flush()
        ids['waiting'] = waiting.id
        db.execute(text("UPDATE clients SET is_penalized = true WHERE id = :id"), {'id': clients[1]})
        db.commit()
        ids['book'] = book_id

    def expiries():
        with engine.connect() as conn:
            return {row.id: row.expires_at for row in conn.execute(text('SELECT id, expires_at FROM purchase_reservations'))}

    assert expiries()[ids['legacy']] is None
    alembic('upgrade', '20261003_0014')
    after = expiries()
    expected = datetime(2026, 10, 8, 23, 59, 59, 999000, tzinfo=timezone(offset=timedelta(hours=-3)))
    assert after[ids['legacy']] == expected  # mesma regra de reservation_pickup_deadline(notified_at)
    assert after[ids['penalized']] == expected  # cliente penalizado não impede o backfill
    assert after[ids['has_deadline']] == datetime(2030, 1, 1, tzinfo=timezone.utc)  # prazo existente é preservado
    assert after[ids['waiting']] is None  # sem destinação, sem prazo
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT status::text FROM purchase_reservations WHERE id = :id"), {'id': ids['penalized']}) == 'NOTIFIED'
        assert conn.scalar(text("SELECT tgenabled FROM pg_trigger WHERE tgname = 'trg_validate_purchase_reservation'")) == 'O'
    from app.core.business_dates import reservation_pickup_deadline
    assert after[ids['legacy']] == reservation_pickup_deadline(notified_at)
    alembic('downgrade', '20261003_0013')  # sem desfazer: os valores são válidos e não são rastreáveis
    assert expiries() == after
    alembic('upgrade', 'head')
    assert expiries() == after
    alembic('check')


def test_waiting_reservation_with_free_copy_is_allowed_only_when_a_queue_exists_and_downgrade_restores(scratch_database):
    engine, alembic = scratch_database
    alembic('upgrade', 'head')
    with Session(engine) as db:
        book_id, (copy_id,) = seed_book(db)
        first, second = make_user(db, 'USER', 'Primeiro'), make_user(db, 'USER', 'Segundo')
        borrower, employee = make_user(db, 'USER', 'Leitor'), db.scalar(select(Employee.id))
        db.commit()
    now = datetime.now(timezone.utc)

    def lend():
        with Session(engine) as db:
            db.add(Loan(client_id=borrower, copy_id=copy_id, employee_id=employee, loan_date=now,
                        due_date=now + timedelta(days=30), status=LoanStatus.OPEN))
            db.commit()

    def give_back():
        with Session(engine) as db:
            db.execute(text("UPDATE loans SET status = 'RETURNED', returned_at = now() WHERE copy_id = :id"), {'id': copy_id})
            db.commit()

    def add_waiting(client):
        with Session(engine) as db:
            db.add(PurchaseReservation(book_id=book_id, client_id=client, status=ReservationStatus.WAITING))
            db.commit()
    with pytest.raises(DBAPIError, match='No commercial copy is expected'):
        add_waiting(first)  # sem fila e com exemplar livre: continua recusado
    lend()
    add_waiting(first)  # fila vazia, exemplar emprestado: aceito
    give_back()
    add_waiting(second)  # há fila WAITING: entra no fim mesmo com exemplar livre
    with engine.connect() as conn:
        assert conn.execute(text("SELECT queue_position FROM purchase_reservations WHERE client_id = :c"),
                            {'c': second}).scalar() == 2
    alembic('downgrade', '20261003_0014')
    with Session(engine) as db:
        third = make_user(db, 'USER', 'Terceiro')
        db.commit()
    with pytest.raises(DBAPIError, match='No commercial copy is expected'):
        add_waiting(third)  # a versão anterior do gatilho volta a valer
    alembic('upgrade', 'head')
    add_waiting(third)
