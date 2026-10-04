"""Issue #154: existing migrated PostgreSQL fixture, never application database."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError, PermissionDeniedError
from app.core.security import hash_password, verify_password
from app.models.domain import AuditLog, Profile
from app.models.user import User
from app.models.user_session import UserSession
from app.repositories.user_repository import UserRepository
from app.repositories.user_session_repository import UserSessionRepository
from app.schemas.user_schema import UserPasswordReset
from app.services.user_service import UserService
from test_client_requests_postgres import records  # noqa: F401
from test_staff_desk_postgres import new_user


def service(db):
    return UserService(db, UserRepository(db), UserSessionRepository(db))


@pytest.fixture
def reset_records(records):
    engine, _, target = records
    with Session(engine) as db:
        actor = new_user(db, 'ADMINISTRATOR', 'Administrador de senha')
        user = db.get(User, target)
        user.password_hash = hash_password('senha-anterior')
        user.is_active = False  # reset must not reactivate an account
        for _ in range(2):
            db.add(UserSession(user_id=target, refresh_token_hash=uuid4().hex,
                               expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
        db.commit()
    return engine, target, actor


def audits(db, target):
    return list(db.scalars(select(AuditLog).where(AuditLog.entity_type == 'users',
                      AuditLog.entity_id == str(target), AuditLog.operation == 'PASSWORD_RESET')))


def test_reset_persists_hash_revocation_and_secret_free_audit(reset_records):
    engine, target, actor = reset_records
    with Session(engine) as db:
        service(db).reset_password(target, UserPasswordReset(new_password='senha-nova-teste'), actor_id=actor)
    with Session(engine) as db:
        user = db.get(User, target)
        assert verify_password('senha-nova-teste', user.password_hash)
        assert not verify_password('senha-anterior', user.password_hash)
        assert user.is_active is False
        assert all(item.revoked_at for item in db.scalars(select(UserSession).where(UserSession.user_id == target)))
        events = audits(db, target)
        assert len(events) == 1 and events[0].employee_id == actor
        assert events[0].old_value is None and events[0].new_value is None


@pytest.mark.parametrize('failure_at', ['commit', 'audit', 'hash'])
def test_failure_rolls_back_password_sessions_and_audit(reset_records, monkeypatch, failure_at):
    engine, target, actor = reset_records
    class FailingSession(Session):
        def commit(self):
            if failure_at == 'commit':
                raise SQLAlchemyError('forced failure')
            super().commit()
    with FailingSession(engine) as db:
        operation = service(db)
        if failure_at == 'audit':
            original_audit = operation.user_repository.audit_password_reset
            def failed_audit(*args):
                original_audit(*args)
                raise SQLAlchemyError('forced failure after audit flush')
            monkeypatch.setattr(operation.user_repository, 'audit_password_reset', failed_audit)
        if failure_at == 'hash':
            def failed_hash(_password):
                raise RuntimeError('forced hashing failure')
            monkeypatch.setattr('app.services.user_service.hash_password', failed_hash)
        with pytest.raises(ApplicationError):
            operation.reset_password(target, UserPasswordReset(new_password='senha-nova-teste'), actor_id=actor)
    with Session(engine) as db:
        assert verify_password('senha-anterior', db.get(User, target).password_hash)
        assert all(item.revoked_at is None for item in db.scalars(select(UserSession).where(UserSession.user_id == target)))
        assert audits(db, target) == []


@pytest.mark.parametrize('state', ['inactive_user', 'inactive_profile', 'seller', 'client'])
def test_repository_rejects_inactive_or_non_administrator_employee(reset_records, state):
    engine, target, actor = reset_records
    with Session(engine) as db:
        if state == 'inactive_user':
            db.get(User, actor).is_active = False
        elif state == 'inactive_profile':
            db.get(Profile, actor).is_active = False
        else:
            actor = new_user(db, 'SELLER' if state == 'seller' else 'USER', 'Outro ator')
        db.commit()
        with pytest.raises(PermissionDeniedError):
            service(db).reset_password(target, UserPasswordReset(new_password='senha-nova-teste'), actor_id=actor)
        assert audits(db, target) == []
        assert verify_password('senha-anterior', db.get(User, target).password_hash)


def test_concurrent_resets_serialize_and_preserve_both_audits(reset_records):
    engine, target, actor = reset_records
    barrier = Barrier(2)
    passwords = ['primeira-senha', 'segunda-senha']
    def reset(password):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            return service(db).reset_password(target, UserPasswordReset(new_password=password), actor_id=actor)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reset, passwords))
    assert all(result.user_id == target for result in results)
    with Session(engine) as db:
        assert len(audits(db, target)) == 2
        assert sum(verify_password(password, db.get(User, target).password_hash) for password in passwords) == 1
        assert all(item.revoked_at for item in db.scalars(select(UserSession).where(UserSession.user_id == target)))
