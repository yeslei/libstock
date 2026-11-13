from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError

from app.core.business_dates import BUSINESS_ZONE
from app.core.exceptions import ApplicationError
from app.models.domain import LoanStatus, NotificationChannel, NotificationStatus, ReservationStatus
from app.repositories.notification_preference_repository import NotificationPreferenceRepository
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification_schema import NotificationPage, NotificationResponse
from app.services.notification_preference_service import NotificationPreferenceService

AVAILABILITY_EVENT = "RESERVATION_AVAILABLE"


class NotificationService:
    def __init__(self, db, repository: NotificationRepository | None = None, preferences=None):
        self.db = db
        self.repository = repository if repository is not None else NotificationRepository(db)
        self.preferences = preferences if preferences is not None else NotificationPreferenceService(
            db, NotificationPreferenceRepository(db))

    def enqueue_availability(self, reservation_id: int) -> None:
        """Called inside the allocation transaction; never sends external mail."""
        data = self.repository.availability_data(reservation_id)
        if data is None:
            raise ApplicationError("Reserva não encontrada.", "reservation_not_found", 404)
        reservation, book, profile, _user = data
        if reservation.status != ReservationStatus.NOTIFIED or reservation.expires_at is None:
            raise ApplicationError("Reserva ainda não disponível.", "reservation_not_ready", 409)
        now = datetime.now(timezone.utc)
        channel = profile.notification_preference
        deadline = reservation.expires_at.astimezone(BUSINESS_ZONE).strftime("%d/%m/%Y às %H:%M")
        self.repository.enqueue(
            user_id=reservation.client_id, reservation_id=reservation.id, type=AVAILABILITY_EVENT,
            channel=channel, subject="Sua reserva está disponível para retirada",
            message=f'O livro “{book.title}” está disponível para retirada no balcão. Retire até {deadline} (horário de São Paulo). Consulte Minhas reservas para acompanhar a situação atual.',
            status=NotificationStatus.SENT if channel == NotificationChannel.IN_APP else NotificationStatus.PENDING,
            sent_at=now if channel == NotificationChannel.IN_APP else None,
        )

    def send_return_reminder(self, loan_id: int) -> NotificationResponse:
        try:
            data = self.repository.return_reminder_data(loan_id)
            if data is None:
                raise ApplicationError("Empréstimo não encontrado.", "loan_not_found", 404)

            loan, book, profile, user = data
            if loan.status != LoanStatus.OPEN:
                raise ApplicationError("Este empréstimo já foi encerrado.", "loan_already_closed", 409)
            if not profile.is_active or not user.is_active:
                raise ApplicationError("O cliente está inativo.", "client_inactive", 403)

            now = datetime.now(timezone.utc)
            # Esta história entrega o lembrete no inbox do LibStock. O envio
            # por e-mail continua pertencendo ao dispatcher de notificações.
            channel = NotificationChannel.IN_APP
            subject = "Lembrete de devolução"
            message = (
                f"Lembrete: devolva “{book.title}” até "
                f"{loan.due_date.astimezone(BUSINESS_ZONE).strftime('%d/%m/%Y às %H:%M')} (horário de São Paulo)."
            )
            item = self.repository.create_return_reminder(
                user_id=loan.client_id,
                channel=channel,
                subject=subject,
                message=message,
                status=NotificationStatus.SENT,
                sent_at=now,
            )
            response = NotificationResponse.model_validate(item)
            self.db.commit()
            return response
        except ApplicationError:
            self.db.rollback()
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ApplicationError(
                "Não foi possível registrar o lembrete de devolução.",
                "return_reminder_persistence_error",
                500,
            ) from exc

    def list_own(self, user_id: int, *, before_id: int | None = None, limit: int = 20) -> NotificationPage:
        try:
            self.preferences.get(user_id)
            records = self.repository.list_own(user_id, before_id=before_id, limit=limit + 1)
            page = records[:limit]
            return NotificationPage(items=[NotificationResponse.model_validate(item) for item in page],
                next_before_id=page[-1].id if len(records) > limit else None)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ApplicationError("Não foi possível consultar as notificações.", "notification_read_error", 500) from exc

    def mark_read(self, user_id: int, notification_id: int) -> NotificationResponse:
        try:
            self.preferences._client(user_id, lock=True)
            item = self.repository.lock_own(notification_id, user_id)
            if item is None:
                raise ApplicationError("Notificação não encontrada.", "notification_not_found", 404)
            if item.status not in (NotificationStatus.SENT, NotificationStatus.READ):
                raise ApplicationError("A notificação ainda não foi entregue.", "notification_not_delivered", 409)
            if item.status == NotificationStatus.SENT:
                item.status = NotificationStatus.READ
                item.read_at = max(datetime.now(timezone.utc), item.sent_at)
            response = NotificationResponse.model_validate(item)
            self.db.commit()
            return response
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ApplicationError("Não foi possível atualizar a notificação.", "notification_persistence_error", 500) from exc
        except ApplicationError:
            self.db.rollback()
            raise
