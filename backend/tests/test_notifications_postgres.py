from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from uuid import uuid4

from app.core.business_dates import business_today
from app.core.exceptions import ApplicationError
from app.models.domain import Employee, Notification, NotificationChannel, NotificationStatus, Profile
from app.repositories.notification_repository import NotificationRepository
from app.repositories.purchase_request_repository import PurchaseRequestRepository
from app.schemas.purchase_request_schema import PurchaseRequestCreate
from app.services.notification_service import NotificationService
from app.services.purchase_request_service import PurchaseRequestService
from test_client_requests_postgres import records
from test_reservation_migrations_postgres import scratch_database, make_user


def create_purchase(db, client_id, book_id):
    return PurchaseRequestService(db, PurchaseRequestRepository(db)).create(
        PurchaseRequestCreate(book_id=book_id, pickup_date=business_today()), client_id=client_id)


def test_waiting_to_notified_allocation_creates_one_notification(records):
    from app.repositories.circulation_repository import CirculationRepository
    from app.services.circulation_service import CirculationService
    from test_reservation_lifecycle_postgres import waiting_queue
    engine, book_id, client_id = records
    with Session(engine) as db:
        employee_id = db.scalar(select(Employee.id).order_by(Employee.id))
    _, reservation_ids, _ = waiting_queue(engine, book_id, client_id, employee_id)
    with Session(engine) as db:
        assert db.scalar(select(Notification.id).where(Notification.user_id == client_id)) is None
        CirculationService(db, CirculationRepository(db)).allocate_purchase(book_id, employee_id)
    with Session(engine) as db:
        item = db.scalar(select(Notification).where(Notification.user_id == client_id))
        assert item.reservation_id == reservation_ids[0] and item.status == NotificationStatus.SENT
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == client_id)) == 1


def test_notification_migration_preserves_legacy_records_and_is_reversible(scratch_database):
    from sqlalchemy import text
    engine, alembic = scratch_database
    alembic('upgrade', '20261004_0017')
    with Session(engine) as db:
        user_id = make_user(db, 'USER', 'Cliente migração')
        # SQL no esquema anterior: o ORM atual já inclui reservation_id.
        db.execute(text("INSERT INTO notifications (user_id, type, channel, message) VALUES (:id, 'LEGACY', 'IN_APP', 'Anterior')"), {'id': user_id})
        db.commit()
    alembic('upgrade', 'head')
    alembic('check')
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM notifications WHERE type = 'LEGACY' AND reservation_id IS NULL")) == 1
        assert conn.scalar(text("SELECT count(*) FROM pg_indexes WHERE indexname = 'uq_notification_reservation_event'")) == 1
    alembic('downgrade', '-1')
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM notifications WHERE type = 'LEGACY'")) == 1
        assert conn.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_name = 'notifications' AND column_name = 'reservation_id'")) == 0
    alembic('upgrade', 'head')
    alembic('check')


@pytest.mark.parametrize("channel,status", [(NotificationChannel.IN_APP, NotificationStatus.SENT),
    (NotificationChannel.EMAIL, NotificationStatus.PENDING)])
def test_purchase_destination_creates_one_transactional_notification(records, channel, status):
    engine, book_id, client_id = records
    with Session(engine) as db:
        db.get(Profile, client_id).notification_preference = channel
        db.commit()
        create_purchase(db, client_id, book_id)
        item = db.scalar(select(Notification).where(Notification.user_id == client_id))
        assert item.status == status and item.channel == channel
        assert item.reservation_id is not None
        reservation_id = item.reservation_id
        NotificationService(db).enqueue_availability(reservation_id)
        db.commit()
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == client_id)) == 1

    # Concurrent repeated event handling cannot create duplicate notifications.
    def enqueue(_):
        with Session(engine) as db:
            NotificationService(db).enqueue_availability(reservation_id)
            db.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(enqueue, range(2)))
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.reservation_id == reservation_id)) == 1


def test_notification_failure_rolls_back_purchase_and_allocation(records):
    engine, book_id, client_id = records

    class FailingRepository(NotificationRepository):
        def enqueue(self, **values):
            super().enqueue(**values)
            raise SQLAlchemyError("forced outbox failure")

    with Session(engine) as db:
        notifications = NotificationService(db, FailingRepository(db))
        service = PurchaseRequestService(db, PurchaseRequestRepository(db), notifications)
        with pytest.raises(ApplicationError) as error:
            service.create(PurchaseRequestCreate(book_id=book_id, pickup_date=business_today()), client_id=client_id)
        assert error.value.code == "purchase_request_persistence_error"
    with Session(engine) as db:
        from app.models.domain import PurchaseReservation
        assert db.scalar(select(Notification.id).where(Notification.user_id == client_id)) is None
        assert db.scalar(select(PurchaseReservation.id).where(PurchaseReservation.book_id == book_id)) is None


def test_own_inbox_read_is_persisted_and_other_identity_gets_404(records):
    engine, book_id, client_id = records
    with Session(engine) as db:
        create_purchase(db, client_id, book_id)
        service = NotificationService(db)
        page = service.list_own(client_id)
        assert len(page.items) == 1
        result = service.mark_read(client_id, page.items[0].id)
        assert result.status == NotificationStatus.READ and result.read_at >= result.sent_at
        from app.models.domain import Client
        from app.models.user import User
        other = User(name="Outro cliente", email=f"{uuid4().hex}@test.invalid", password_hash="test")
        db.add(other); db.flush()
        db.add(Profile(id=other.id)); db.flush()
        db.add(Client(id=other.id)); db.commit()
        assert service.list_own(other.id).items == []
        with pytest.raises(ApplicationError) as error:
            service.mark_read(other.id, page.items[0].id)
        assert error.value.code == "notification_not_found"
