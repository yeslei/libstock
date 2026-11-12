"""Integração em PostgreSQL migrado por Alembic, incluindo duas sessões reais."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import engine
from app.core.exceptions import ActiveEmployeeRequiredError, CopyStateConflictError, CopyUpdatePersistenceError
from app.models.domain import AuditLog, Book, Client, Copy, CopyStatus, Employee, Loan, Profile, Role, UserRole
from app.models.user import User
from app.repositories.copy_repository import CopyRepository
from app.schemas.copy_schema import CopyStatusUpdate
from app.services.copy_service import CopyService


@pytest.fixture
def inventory():
    token = uuid4().hex
    with Session(engine, expire_on_commit=False) as db:
        user = User(name='Status test', email=f'{token}@example.test', password_hash='unused')
        db.add(user)
        db.flush()
        profile = Profile(id=user.id)
        db.add(profile)
        db.flush()
        role = db.scalar(select(Role).where(Role.code == 'STOCK_KEEPER'))
        db.add_all([Employee(id=user.id, employee_code=token, role_id=role.id),
                    UserRole(user_id=user.id, role_id=role.id), Client(id=user.id)])
        db.flush()
        repo = CopyRepository(db)
        repo.set_audit_actor(user.id)
        book = Book(title='Status test', author='Test')
        db.add(book)
        db.flush()
        copy = Copy(book_id=book.id, barcode=token, destination='DIDACTIC')
        db.add(copy)
        db.commit()
        db.refresh(copy)
        ids = user.id, book.id, copy.id, copy.updated_at
    try:
        yield ids
    finally:
        with engine.begin() as conn:
            conn.execute(text("SELECT set_config('libstock.employee_id', :actor, true)"), {'actor': str(ids[0])})
            conn.execute(delete(Loan).where(Loan.copy_id == ids[2]))
            conn.execute(delete(Copy).where(Copy.id == ids[2]))
            conn.execute(delete(Book).where(Book.id == ids[1]))
            # Test-only cleanup, following the existing immutable-audit integration fixture.
            conn.execute(text('ALTER TABLE audit_logs DISABLE TRIGGER trg_prevent_audit_log_modification'))
            conn.execute(delete(AuditLog).where(AuditLog.employee_id == ids[0]))
            conn.execute(text('ALTER TABLE audit_logs ENABLE TRIGGER trg_prevent_audit_log_modification'))
            conn.execute(delete(User).where(User.id == ids[0]))


def update(db, ids, status='INACTIVE', expected=None):
    return CopyService(CopyRepository(db), db).update_status(
        ids[2], CopyStatusUpdate(status=status, expected_updated_at=expected or ids[3]), actor_id=ids[0])


def test_persists_status_audit_and_availability_without_changing_identity(inventory):
    with Session(engine) as db:
        result = update(db, inventory)
        assert result.status == CopyStatus.INACTIVE
        assert result.is_active is True
        assert result.updated_at != inventory[3]
    with Session(engine) as db:
        copy = db.get(Copy, inventory[2])
        assert copy.status == CopyStatus.INACTIVE
        assert copy.barcode == result.barcode
        assert copy.is_active is True
        assert db.scalar(select(func.count()).select_from(Copy).where(
            Copy.book_id == inventory[1], Copy.status == CopyStatus.AVAILABLE, Copy.is_active.is_(True))) == 0
        audit = db.scalar(select(AuditLog).where(AuditLog.entity_type == 'copies',
            AuditLog.entity_id == str(copy.id), AuditLog.operation == 'UPDATE'))
        assert audit.employee_id == inventory[0]
        assert audit.old_value['status'] == 'AVAILABLE'
        assert audit.new_value['status'] == 'INACTIVE'
        restored = update(db, inventory, 'AVAILABLE', result.updated_at)
        assert restored.status == CopyStatus.AVAILABLE


@pytest.mark.parametrize('field', ['profile', 'user'])
def test_inactive_actor_rejected_by_real_repository(inventory, field):
    with Session(engine) as db:
        item = db.get(Profile if field == 'profile' else User, inventory[0])
        item.is_active = False
        db.commit()
        with pytest.raises(ActiveEmployeeRequiredError):
            update(db, inventory)
        assert db.get(Copy, inventory[2]).status == CopyStatus.AVAILABLE


def test_commit_failure_rolls_back_status_and_audit(inventory):
    class FailedCommitSession(Session):
        def commit(self):
            raise SQLAlchemyError('injected commit failure after flush')
    with FailedCommitSession(engine) as db:
        with pytest.raises(CopyUpdatePersistenceError):
            update(db, inventory)
    with Session(engine) as db:
        assert db.get(Copy, inventory[2]).status == CopyStatus.AVAILABLE
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.entity_type == 'copies', AuditLog.entity_id == str(inventory[2]), AuditLog.operation == 'UPDATE')) == 0


def test_unique_barcode_remains_enforced(inventory):
    with Session(engine) as db:
        result = update(db, inventory)
        CopyRepository(db).set_audit_actor(inventory[0])
        db.add(Copy(book_id=inventory[1], barcode=result.barcode, destination='DIDACTIC'))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
        assert db.get(Copy, inventory[2]).status == CopyStatus.INACTIVE


@pytest.mark.parametrize('competing_operation', ['manual', 'loan'])
def test_concurrent_operation_does_not_overwrite_committed_state(inventory, competing_operation):
    attempted = Event()

    class ObservedRepository(CopyRepository):
        def find_for_update(self, copy_id):
            attempted.set()
            return super().find_for_update(copy_id)

    def competing_update():
        with Session(engine) as db:
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
            service = CopyService(ObservedRepository(db), db)
            with pytest.raises(CopyStateConflictError):
                service.update_status(inventory[2], CopyStatusUpdate(
                    status='INACTIVE', expected_updated_at=inventory[3]), actor_id=inventory[0])

    with Session(engine, expire_on_commit=False) as first:
        repo = CopyRepository(first)
        copy = repo.find_for_update(inventory[2])
        repo.set_audit_actor(inventory[0])
        if competing_operation == 'manual':
            repo.update_status(copy, CopyStatus.INACTIVE)
        else:
            now = datetime.now(timezone.utc)
            first.add(Loan(copy_id=copy.id, client_id=inventory[0], employee_id=inventory[0],
                           loan_date=now, due_date=now + timedelta(days=15)))
            first.flush()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(competing_update)
            assert attempted.wait(3)
            first.commit()
            future.result(timeout=10)
    with Session(engine) as db:
        expected = CopyStatus.INACTIVE if competing_operation == 'manual' else CopyStatus.BORROWED
        assert db.get(Copy, inventory[2]).status == expected


def test_http_read_update_read_and_stale_conflict(inventory):
    from fastapi.testclient import TestClient
    from types import SimpleNamespace
    from app.dependencies.authentication import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=inventory[0], role_codes=['STOCK_KEEPER'])
    try:
        with TestClient(app) as client:
            before = client.get(f'/api/v1/books/{inventory[1]}')
            assert before.status_code == 200
            copy = before.json()['copies'][0]
            body = {'status': 'INACTIVE', 'expected_updated_at': copy['updated_at']}
            changed = client.patch(f'/api/v1/copies/{inventory[2]}/status', json=body)
            assert changed.status_code == 200
            after = client.get(f'/api/v1/books/{inventory[1]}').json()['copies'][0]
            assert after['status'] == 'INACTIVE'
            assert after['updated_at'] == changed.json()['updated_at']
            stale = client.patch(f'/api/v1/copies/{inventory[2]}/status', json=body)
            assert stale.status_code == 409
            assert stale.json()['code'] == 'copy_state_conflict'
    finally:
        app.dependency_overrides.clear()


def test_noop_preserves_timestamp_and_audit(inventory):
    with Session(engine) as db:
        result = update(db, inventory, 'AVAILABLE')
        assert result.updated_at == inventory[3]
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.entity_type == 'copies', AuditLog.entity_id == str(inventory[2]), AuditLog.operation == 'UPDATE')) == 0


def test_is_active_false_remains_false(inventory):
    with Session(engine) as db:
        repo = CopyRepository(db)
        repo.set_audit_actor(inventory[0])
        db.get(Book, inventory[1]).is_active = False
        copy = db.get(Copy, inventory[2])
        copy.is_active = False
        db.commit()
        db.refresh(copy)
        result = update(db, inventory, expected=copy.updated_at)
        assert result.is_active is False
        restored = update(db, inventory, 'AVAILABLE', result.updated_at)
        assert restored.is_active is False


def test_missing_audit_context_rolls_back_real_trigger(inventory):
    class MissingAuditRepository(CopyRepository):
        def set_audit_actor(self, employee_id):
            pass
    with Session(engine) as db:
        with pytest.raises(CopyUpdatePersistenceError):
            CopyService(MissingAuditRepository(db), db).update_status(
                inventory[2], CopyStatusUpdate(status='INACTIVE', expected_updated_at=inventory[3]), actor_id=inventory[0])
    with Session(engine) as db:
        assert db.get(Copy, inventory[2]).status == CopyStatus.AVAILABLE
