from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ClientNotFoundError,
    ClientPenaltyApplicationError,
    ClientPenaltyPersistenceError,
    ClientPenaltyRemovalError,
    EmployeeRecordRequiredError,
)
from app.repositories.client_pendency_repository import ClientPendencyRepository
from app.schemas.client_pendency_schema import (
    ClientPendencyResponse,
    OverdueLoanResponse,
    PenaltyAction,
)


class ClientPendencyService:
    def __init__(
        self,
        db: Session,
        repository: ClientPendencyRepository,
    ) -> None:
        self.db = db
        self.repository = repository

    def get_pendencies(self, client_id: int) -> ClientPendencyResponse:
        try:
            client = self._get_client(client_id)

            overdue_loans = self.repository.list_overdue_loans(client_id)
            has_pending = bool(overdue_loans)

            changed = self._synchronize_penalty(
                client=client,
                has_pending=has_pending,
                reason=self._automatic_reason(has_pending),
                actor_type="SYSTEM",
                employee_id=None,
            )

            if changed:
                self.db.commit()

            return self._build_response(
                client_id=client.id,
                is_penalized=has_pending,
                overdue_loans=overdue_loans,
            )

        except (ClientNotFoundError,):
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ClientPenaltyPersistenceError() from exc

    def change_penalty(
        self,
        *,
        client_id: int,
        action: PenaltyAction,
        reason: str,
        actor_id: int,
    ) -> ClientPendencyResponse:
        try:
            employee = self.repository.find_employee_by_id(actor_id)

            if employee is None:
                raise EmployeeRecordRequiredError()

            client = self._get_client(client_id)

            overdue_loans = self.repository.list_overdue_loans(client_id)
            has_pending = bool(overdue_loans)

            if action == "APPLY":
                if not has_pending:
                    raise ClientPenaltyApplicationError()

                target_state = True

            else:
                if has_pending:
                    raise ClientPenaltyRemovalError()

                target_state = False

            old_state = client.is_penalized

            if old_state != target_state:
                self.repository.update_penalized(
                    client,
                    target_state,
                )

                self.repository.record_penalty_change(
                    client_id=client.id,
                    action=(
                        "PENALTY_APPLIED"
                        if target_state
                        else "PENALTY_REMOVED"
                    ),
                    old_value=old_state,
                    new_value=target_state,
                    reason=reason,
                    actor_type="EMPLOYEE",
                    employee_id=actor_id,
                )

            self.db.commit()

            return self._build_response(
                client_id=client.id,
                is_penalized=target_state,
                overdue_loans=overdue_loans,
            )

        except (
            ClientNotFoundError,
            ClientPenaltyApplicationError,
            ClientPenaltyRemovalError,
            EmployeeRecordRequiredError,
        ):
            self.db.rollback()
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ClientPenaltyPersistenceError() from exc

    def synchronize_penalty(
        self,
        *,
        client_id: int,
        reason: str,
        actor_type: str = "SYSTEM",
        employee_id: int | None = None,
    ) -> bool:
        """
        Sincroniza a penalização do cliente dentro da transação atual.

        Este método é destinado a outros fluxos do domínio, como devolução
        de empréstimo. Não executa commit.
        """
        client = self._get_client(client_id)

        overdue_loans = self.repository.list_overdue_loans(client_id)

        return self._synchronize_penalty(
            client=client,
            has_pending=bool(overdue_loans),
            reason=reason,
            actor_type=actor_type,
            employee_id=employee_id,
        )

    def _synchronize_penalty(
        self,
        *,
        client,
        has_pending: bool,
        reason: str,
        actor_type: str,
        employee_id: int | None,
    ) -> bool:
        desired_state = has_pending

        if client.is_penalized == desired_state:
            return False

        old_state = client.is_penalized

        self.repository.update_penalized(
            client,
            desired_state,
        )

        self.repository.record_penalty_change(
            client_id=client.id,
            action=(
                "PENALTY_APPLIED"
                if desired_state
                else "PENALTY_REMOVED"
            ),
            old_value=old_state,
            new_value=desired_state,
            reason=reason,
            actor_type=actor_type,
            employee_id=employee_id,
        )

        return True

    def _get_client(self, client_id: int):
        client = self.repository.find_client_for_update(client_id)

        if client is None:
            raise ClientNotFoundError()

        return client

    @staticmethod
    def _automatic_reason(has_pending: bool) -> str:
        if has_pending:
            return "Empréstimo em atraso detectado automaticamente."

        return "Todos os empréstimos em atraso foram regularizados."

    @staticmethod
    def _build_response(
        *,
        client_id: int,
        is_penalized: bool,
        overdue_loans: list[dict],
    ) -> ClientPendencyResponse:
        return ClientPendencyResponse(
            client_id=client_id,
            has_pending=bool(overdue_loans),
            is_penalized=is_penalized,
            overdue_loans=[
                OverdueLoanResponse(**loan)
                for loan in overdue_loans
            ],
        )