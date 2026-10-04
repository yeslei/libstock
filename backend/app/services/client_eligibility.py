from datetime import date
from app.core.business_dates import overdue_cutoff
from app.core.exceptions import ApplicationError
from app.repositories.client_request_repository import ClientRequestRepository


def is_client_eligible(*, profile_active: bool, user_active: bool, penalized: bool, has_overdue: bool) -> bool:
    """Single eligibility predicate shared by writes (locked) and read-only listings."""
    return profile_active and user_active and not penalized and not has_overdue


def require_eligible_client(repository: ClientRequestRepository, client_id: int, today: date) -> None:
    records = repository.lock_client(client_id)
    if records is None:
        raise ApplicationError("É necessário um cadastro de cliente.", "client_required", 403)
    client, profile, user = records
    if not is_client_eligible(
        profile_active=profile.is_active, user_active=user.is_active, penalized=client.is_penalized,
        has_overdue=repository.has_overdue_loan(client_id, overdue_cutoff(today)),
    ):
        raise ApplicationError("Cliente inativo, penalizado ou com empréstimo em atraso.", "client_ineligible", 403)


def is_client_locked_eligible(repository: ClientRequestRepository, client_id: int, today: date) -> bool:
    """Non-raising variant of require_eligible_client: locks the client and tells whether it is eligible."""
    try:
        require_eligible_client(repository, client_id, today)
    except ApplicationError:
        return False
    return True
