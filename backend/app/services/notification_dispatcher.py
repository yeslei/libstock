from datetime import datetime, timezone
from email.errors import MessageError
import smtplib

from app.core.mail import MailDeliveryError, OutgoingMail
from app.models.domain import NotificationChannel, NotificationStatus, ReservationStatus
from app.repositories.notification_preference_repository import NotificationPreferenceRepository
from app.repositories.notification_repository import NotificationRepository


class NotificationDispatcher:
    """At-most-once delivery attempt; uncertainty stays FAILED for reconciliation."""
    def __init__(self, session_factory, sender):
        self.session_factory = session_factory
        self.sender = sender

    def _claim(self, db, candidate):
        repo = NotificationRepository(db)
        notification_id, book_id, reservation_id = candidate
        # Same ordering as circulation: book -> reservation -> client -> notification.
        # mark_read only locks client -> notification; it never waits for a book.
        book = repo.lock_book_for_dispatch(book_id)
        if book is None:
            return None
        reservation = repo.lock_reservation_for_dispatch(reservation_id)
        if reservation is None:
            return None
        records = NotificationPreferenceRepository(db).find_client(reservation.client_id, lock=True)
        item = repo.lock_for_dispatch(notification_id)
        if item is None:
            return None
        # Acquiring any lock may have waited across the pickup deadline.
        now = datetime.now(timezone.utc)
        # Claim durably before any external effect. A crash must not cause resend.
        item.status = NotificationStatus.FAILED
        valid = records is not None and book.is_active and reservation.status == ReservationStatus.NOTIFIED
        valid = valid and reservation.expires_at is not None and reservation.expires_at >= now
        if records is not None:
            profile, user = records
            valid = valid and profile.is_active and user.is_active and "USER" in user.role_codes
            valid = valid and profile.notification_preference == NotificationChannel.EMAIL
        if not valid:
            db.commit()
            return None
        mail = OutgoingMail(notification_id=item.id, recipient=user.email,
            subject=item.subject or "Notificação do LibStock", message=item.message)
        db.commit()
        return mail

    def dispatch_batch(self, *, limit: int = 50) -> dict[str, int]:
        with self.session_factory() as db:
            candidates = NotificationRepository(db).pending_candidates(limit)
        result = {"examined": len(candidates), "sent": 0, "unconfirmed": 0}
        for candidate in candidates:
            with self.session_factory() as db:
                mail = self._claim(db, candidate)
            if mail is None:
                continue
            try:
                self.sender.send(mail)
            except (OSError, smtplib.SMTPException, ValueError, MessageError, MailDeliveryError):
                result["unconfirmed"] += 1
                continue
            with self.session_factory() as db:
                NotificationRepository(db).confirm_sent(mail.notification_id, datetime.now(timezone.utc))
                db.commit()
            result["sent"] += 1
        return result
