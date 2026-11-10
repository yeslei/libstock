from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, Mock, patch
import smtplib

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.models.domain import NotificationChannel as Channel, NotificationStatus as Status, ReservationStatus
from app.core.mail import MailDeliveryError
from app.services.notification_dispatcher import NotificationDispatcher


@pytest.fixture
def dispatch():
    db, sender = MagicMock(), Mock()
    factory = MagicMock()
    factory.return_value.__enter__.return_value = db
    repo = Mock()
    profile = NS(is_active=True, notification_preference=Channel.EMAIL)
    user = NS(is_active=True, role_codes=["USER"], email="current@example.org")
    reservation = NS(client_id=7, status=ReservationStatus.NOTIFIED,
        expires_at=datetime.now(timezone.utc) + timedelta(days=2))
    book = NS(is_active=True)
    item = NS(id=12, status=Status.PENDING, subject="Disponível", message="Retire no balcão.")
    repo.pending_candidates.side_effect = lambda limit: [(12, 3, 5)] if item.status == Status.PENDING else []
    repo.lock_book_for_dispatch.return_value = book
    repo.lock_reservation_for_dispatch.return_value = reservation
    repo.lock_for_dispatch.return_value = item
    def confirm(notification_id, now):
        item.status = Status.SENT
    repo.confirm_sent.side_effect = confirm
    with patch("app.services.notification_dispatcher.NotificationRepository", return_value=repo), \
         patch("app.services.notification_dispatcher.NotificationPreferenceRepository") as preferences:
        preferences.return_value.find_client.return_value = (profile, user)
        yield NotificationDispatcher(factory, sender), db, sender, repo, profile, user, reservation, book, item


def test_claim_is_committed_before_send_and_success_is_recorded(dispatch):
    target, db, sender, _, _, _, _, _, item = dispatch
    def send(mail):
        assert item.status == Status.FAILED
        db.commit.assert_called_once()
        assert mail.recipient == "current@example.org"
    sender.send.side_effect = send
    assert target.dispatch_batch() == {"examined": 1, "sent": 1, "unconfirmed": 0}
    assert item.status == Status.SENT and db.commit.call_count == 2


@pytest.mark.parametrize("failure", [smtplib.SMTPServerDisconnected("connection lost after DATA"),
                                     MailDeliveryError("O provedor não confirmou o envio.")])
def test_ambiguous_delivery_failure_is_not_retried(dispatch, failure):
    target, _, sender, _, _, _, _, _, item = dispatch
    sender.send.side_effect = failure
    assert target.dispatch_batch()["unconfirmed"] == 1
    assert item.status == Status.FAILED
    assert target.dispatch_batch()["examined"] == 0
    sender.send.assert_called_once()


@pytest.mark.parametrize("condition", ["profile", "user", "role", "opt_out", "reservation", "expired", "book"])
def test_claim_rechecks_account_preference_and_reservation(dispatch, condition):
    target, db, sender, _, profile, user, reservation, book, item = dispatch
    if condition == "profile": profile.is_active = False
    if condition == "user": user.is_active = False
    if condition == "role": user.role_codes = ["SELLER"]
    if condition == "opt_out": profile.notification_preference = Channel.IN_APP
    if condition == "reservation": reservation.status = ReservationStatus.CANCELLED
    if condition == "expired": reservation.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    if condition == "book": book.is_active = False
    assert target.dispatch_batch()["sent"] == 0
    assert item.status == Status.FAILED
    sender.send.assert_not_called()
    db.commit.assert_called_once()


def test_failed_claim_commit_never_sends(dispatch):
    target, db, sender, _, _, _, _, _, _ = dispatch
    db.commit.side_effect = SQLAlchemyError("failure")
    with pytest.raises(SQLAlchemyError):
        target.dispatch_batch()
    sender.send.assert_not_called()


def test_lock_contention_skips_without_consuming_pending_message(dispatch):
    target, db, sender, repo, _, _, _, _, item = dispatch
    repo.lock_book_for_dispatch.return_value = None
    target.dispatch_batch()
    assert item.status == Status.PENDING
    sender.send.assert_not_called()
    db.commit.assert_not_called()


def test_deadline_is_checked_with_clock_after_all_locks(dispatch):
    target, _, sender, repo, _, _, reservation, _, item = dispatch
    acquired = []
    def lock(_id):
        acquired.append(True)
        return item
    repo.lock_for_dispatch.side_effect = lock
    def now(_zone):
        assert acquired, "clock must be read after the final lock"
        return reservation.expires_at + timedelta(seconds=1)
    with patch("app.services.notification_dispatcher.datetime") as clock:
        clock.now.side_effect = now
        target.dispatch_batch()
    assert item.status == Status.FAILED
    sender.send.assert_not_called()


def test_database_failure_after_smtp_acceptance_does_not_trigger_resend(dispatch):
    target, _, sender, repo, _, _, _, _, item = dispatch
    repo.confirm_sent.side_effect = SQLAlchemyError("confirmation failed after external effect")
    with pytest.raises(SQLAlchemyError):
        target.dispatch_batch()
    assert item.status == Status.FAILED
    assert target.dispatch_batch()["examined"] == 0
    sender.send.assert_called_once()
