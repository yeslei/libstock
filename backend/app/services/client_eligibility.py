from datetime import date
from app.core.business_dates import business_today, overdue_cutoff
from app.core.exceptions import ApplicationError
from app.repositories.client_request_repository import ClientRequestRepository
from app.schemas.client_eligibility_schema import EligibilityReason, EligibilityResponse


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


INELIGIBILITY_MESSAGES = {
    "inactive": "Conta inativa.",
    "penalized": "Cliente com penalidade ativa.",
    "overdue_loan": "Há empréstimo em atraso.",
}


class ClientEligibilityService:
    """Consulta somente leitura da situação do próprio cliente.

    Usa o mesmo predicado das escritas (`is_client_eligible`) e o atraso da
    regra V2 (data de negócio de São Paulo). Não sincroniza penalidade nem
    bloqueia linhas: informar não é decidir.
    """

    def __init__(self, repository: ClientRequestRepository) -> None:
        self.repository = repository

    def check(self, client_id: int) -> EligibilityResponse:
        records = self.repository.find_client(client_id)
        if records is None:
            raise ApplicationError("É necessário um cadastro de cliente.", "client_required", 403)
        client, profile, user = records
        overdue = self.repository.has_overdue_loan(client_id, overdue_cutoff(business_today()))
        eligible = is_client_eligible(
            profile_active=profile.is_active, user_active=user.is_active,
            penalized=client.is_penalized, has_overdue=overdue,
        )
        codes = []
        if not (profile.is_active and user.is_active):
            codes.append("inactive")
        if client.is_penalized:
            codes.append("penalized")
        if overdue:
            codes.append("overdue_loan")
        return EligibilityResponse(
            eligible=eligible,
            reasons=[EligibilityReason(code=code, message=INELIGIBILITY_MESSAGES[code]) for code in codes],
        )
