from datetime import date, datetime, time
from app.core.business_dates import BUSINESS_ZONE
from app.core.exceptions import ApplicationError
from app.repositories.client_request_repository import ClientRequestRepository


def require_eligible_client(repository: ClientRequestRepository, client_id: int, today: date) -> None:
    records = repository.lock_client(client_id)
    if records is None:
        raise ApplicationError("É necessário um cadastro de cliente.", "client_required", 403)
    client, profile, user = records
    if (not profile.is_active or not user.is_active or client.is_penalized
            or repository.has_overdue_loan(client_id, datetime.combine(today, time.min, BUSINESS_ZONE))):
        raise ApplicationError("Cliente inativo, penalizado ou com empréstimo em atraso.", "client_ineligible", 403)
