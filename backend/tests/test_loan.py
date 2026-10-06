from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import status

from app.core.exceptions import ApplicationError

from app.controllers.loan_controller import create_loan
from app.core.exceptions import ClientHasPendingError, ClientInactiveError
from app.dependencies.authentication import require_roles
from app.core.business_dates import BUSINESS_ZONE, loan_due_at, overdue_cutoff
from app.core.exceptions import CopyNotForLoanError
from app.models.domain import CopyStatus, DestinationType, LoanStatus
from app.schemas.loan_schema import LoanCreate
from app.services.loan_service import LoanService


def _loan_data() -> LoanCreate:
    return LoanCreate(
        client_id=42,
        copy_id=15,
    )


class FakeLoanService:
    def __init__(self) -> None:
        self.created = []

    def create_loan(self, loan_data: LoanCreate, *, employee_id: int):
        self.created.append((loan_data, employee_id))

        loan_date = datetime(2026, 9, 26, 14, 0, tzinfo=timezone.utc)
        due_date = loan_due_at(loan_date)

        return SimpleNamespace(
            id=100,
            client_id=loan_data.client_id,
            copy_id=loan_data.copy_id,
            employee_id=employee_id,
            loan_date=loan_date,
            due_date=due_date,
            returned_at=None,
            status=LoanStatus.OPEN,
        )


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.refreshed = []

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, obj):
        self.refreshed.append(obj)


def _available_copy():
    return SimpleNamespace(
        id=15,
        is_active=True,
        status=CopyStatus.AVAILABLE,
        destination=DestinationType.DIDACTIC,
    )

def _open_loan():
    return SimpleNamespace(
        id=100,
        client_id=42,
        copy_id=15,
        employee_id=7,
        loan_date=datetime(2026, 9, 26, 14, 0, tzinfo=timezone.utc),
        due_date=datetime(2026, 10, 1, 18, 0, tzinfo=timezone.utc),
        returned_at=None,
        status=LoanStatus.OPEN,
    )


def _borrowed_copy():
    return SimpleNamespace(
        id=15,
        is_active=True,
        status=CopyStatus.BORROWED,
    )


def _loan_entity(
    loan_data: LoanCreate,
    employee_id: int,
    loan_date: datetime,
    due_date: datetime,
):
    return SimpleNamespace(
        id=100,
        client_id=loan_data.client_id,
        copy_id=loan_data.copy_id,
        employee_id=employee_id,
        loan_date=loan_date,
        due_date=due_date,
        returned_at=None,
        status=LoanStatus.OPEN,
    )


def test_controller_passa_usuario_para_o_service():
    service = FakeLoanService()

    response = create_loan(
        loan_data=_loan_data(),
        current_user=SimpleNamespace(id=7),
        loan_service=service,
    )

    loan_data, employee_id = service.created[0]

    assert loan_data.client_id == 42
    assert loan_data.copy_id == 15
    assert employee_id == 7
    assert response.id == 100
    assert response.status == LoanStatus.OPEN


def test_endpoint_mantem_contrato_de_criacao():
    service = FakeLoanService()

    response = create_loan(
        loan_data=_loan_data(),
        current_user=SimpleNamespace(id=7),
        loan_service=service,
    )

    assert response.status == LoanStatus.OPEN
    assert response.returned_at is None
    assert response.client_id == 42
    assert response.copy_id == 15
    assert response.employee_id == 7


def test_roles_permitidos_sao_seller_e_administrator():
    dependency = require_roles("SELLER", "ADMINISTRATOR")

    dependency(SimpleNamespace(role_codes=["SELLER"]))
    dependency(SimpleNamespace(role_codes=["ADMINISTRATOR"]))


def test_role_user_nao_pode_criar_emprestimo():
    dependency = require_roles("SELLER", "ADMINISTRATOR")

    with pytest.raises(Exception):
        dependency(SimpleNamespace(role_codes=["USER"]))


def test_service_calcula_prazo_de_um_mes_de_calendario(monkeypatch):
    frozen = datetime(2027, 1, 31, 15, 0, tzinfo=timezone.utc)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen

    monkeypatch.setattr("app.services.loan_service.datetime", FrozenDatetime)
    repository = MagicMock()
    db = FakeSession()
    client_service = MagicMock()

    repository.find_copy_for_loan.return_value = _available_copy()

    def create_loan_side_effect(
        loan_data,
        *,
        employee_id,
        loan_date,
        due_date,
    ):
        return _loan_entity(
            loan_data,
            employee_id,
            loan_date,
            due_date,
        )

    repository.create_loan.side_effect = create_loan_side_effect

    service = LoanService(
        repository=repository,
        db=db,
        client_pendency_service=client_service,
    )

    result = service.create_loan(
        _loan_data(),
        employee_id=7,
    )

    client_service.validate_client_for_operation.assert_called_once_with(
        42,
        commit=False,
    )

    repository.find_copy_for_loan.assert_called_once_with(15)
    repository.create_loan.assert_called_once()

    _, kwargs = repository.create_loan.call_args

    loan_date = kwargs["loan_date"]
    due_date = kwargs["due_date"]

    assert loan_date.tzinfo == timezone.utc
    assert loan_date == frozen
    assert due_date == datetime(2027, 2, 28, 15, 0, tzinfo=timezone.utc)

    assert result.loan_date == loan_date
    assert result.due_date == due_date

    assert db.commits == 1
    assert db.rollbacks == 0


def test_service_faz_rollback_se_exemplar_nao_for_encontrado():
    repository = MagicMock()
    db = FakeSession()
    client_service = MagicMock()

    repository.find_copy_for_loan.return_value = None

    service = LoanService(
        repository=repository,
        db=db,
        client_pendency_service=client_service,
    )

    with pytest.raises(ApplicationError) as exc:
        service.create_loan(
            _loan_data(),
            employee_id=7,
        )

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert db.rollbacks == 1
    assert db.commits == 0
    repository.create_loan.assert_not_called()


def test_service_rejeita_exemplar_indisponivel():
    repository = MagicMock()
    db = FakeSession()
    client_service = MagicMock()

    unavailable_copy = SimpleNamespace(
        id=15,
        is_active=True,
        status=CopyStatus.BORROWED,
    )
    repository.find_copy_for_loan.return_value = unavailable_copy

    service = LoanService(
        repository=repository,
        db=db,
        client_pendency_service=client_service,
    )

    with pytest.raises(ApplicationError) as exc:
        service.create_loan(
            _loan_data(),
            employee_id=7,
        )

    assert exc.value.status_code == status.HTTP_409_CONFLICT
    assert db.rollbacks == 1
    assert db.commits == 0
    repository.create_loan.assert_not_called()


def test_service_propaga_cliente_inativo():
    repository = MagicMock()
    db = FakeSession()
    client_service = MagicMock()

    client_service.validate_client_for_operation.side_effect = ClientInactiveError()

    service = LoanService(
        repository=repository,
        db=db,
        client_pendency_service=client_service,
    )

    with pytest.raises(ClientInactiveError):
        service.create_loan(
            _loan_data(),
            employee_id=7,
        )

    repository.find_copy_for_loan.assert_not_called()
    repository.create_loan.assert_not_called()


def test_service_propaga_cliente_com_pendencia():
    repository = MagicMock()
    db = FakeSession()
    client_service = MagicMock()

    client_service.validate_client_for_operation.side_effect = ClientHasPendingError()

    service = LoanService(
        repository=repository,
        db=db,
        client_pendency_service=client_service,
    )

    with pytest.raises(ClientHasPendingError):
        service.create_loan(
            _loan_data(),
            employee_id=7,
        )

    repository.find_copy_for_loan.assert_not_called()
    repository.create_loan.assert_not_called()


def test_service_trata_erro_de_integridade_com_rollback():
    from sqlalchemy.exc import IntegrityError

    repository = MagicMock()
    db = FakeSession()
    client_service = MagicMock()

    repository.find_copy_for_loan.return_value = _available_copy()
    repository.create_loan.side_effect = IntegrityError(
        "insert",
        {},
        Exception("duplicate open loan"),
    )

    service = LoanService(
        repository=repository,
        db=db,
        client_pendency_service=client_service,
    )

    with pytest.raises(ApplicationError) as exc:
        service.create_loan(
            _loan_data(),
            employee_id=7,
        )

    assert exc.value.status_code == status.HTTP_409_CONFLICT
    assert db.rollbacks == 1
    assert db.commits == 0


def test_service_trata_falha_de_banco_com_rollback():
    from sqlalchemy.exc import SQLAlchemyError

    class DatabaseError(SQLAlchemyError):
        pass

    repository = MagicMock()
    db = FakeSession()
    client_service = MagicMock()

    repository.find_copy_for_loan.return_value = _available_copy()
    repository.create_loan.side_effect = DatabaseError("database error")

    service = LoanService(
        repository=repository,
        db=db,
        client_pendency_service=client_service,
    )

    with pytest.raises(ApplicationError) as exc:
        service.create_loan(
            _loan_data(),
            employee_id=7,
        )

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert db.rollbacks == 1
    assert db.commits == 0

def test_service_registra_devolucao_e_libera_exemplar():
    repository = MagicMock()
    db = FakeSession()
    client_service = MagicMock()

    loan = _open_loan()
    copy = _borrowed_copy()

    repository.find_loan_for_return.return_value = loan
    repository.find_copy_for_return.return_value = copy

    def register_return_side_effect(
        loan,
        copy,
        *,
        returned_at,
    ):
        loan.returned_at = returned_at
        loan.status = LoanStatus.RETURNED
        copy.status = CopyStatus.AVAILABLE
        return loan

    repository.register_return.side_effect = register_return_side_effect

    service = LoanService(
        repository=repository,
        db=db,
        client_pendency_service=client_service,
    )

    result = service.register_return(loan_id=100)

    repository.find_loan_for_return.assert_called_once_with(100)
    repository.find_copy_for_return.assert_called_once_with(15)
    repository.register_return.assert_called_once()

    assert result.status == LoanStatus.RETURNED
    assert result.returned_at is not None
    assert result.returned_at.tzinfo == timezone.utc
    assert copy.status == CopyStatus.AVAILABLE
    assert db.commits == 1
    assert db.rollbacks == 0

def test_service_rejeita_devolucao_de_emprestimo_inexistente():
    repository = MagicMock()
    db = FakeSession()
    client_service = MagicMock()

    repository.find_loan_for_return.return_value = None

    service = LoanService(
        repository=repository,
        db=db,
        client_pendency_service=client_service,
    )

    with pytest.raises(ApplicationError) as exc:
        service.register_return(loan_id=999)

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert db.rollbacks == 1
    assert db.commits == 0
    repository.find_copy_for_return.assert_not_called()
    repository.register_return.assert_not_called()

def test_service_rejeita_devolucao_de_emprestimo_ja_encerrado():
    repository = MagicMock()
    db = FakeSession()
    client_service = MagicMock()

    loan = _open_loan()
    loan.status = LoanStatus.RETURNED
    loan.returned_at = datetime(
        2026,
        9,
        30,
        14,
        0,
        tzinfo=timezone.utc,
    )

    repository.find_loan_for_return.return_value = loan

    service = LoanService(
        repository=repository,
        db=db,
        client_pendency_service=client_service,
    )

    with pytest.raises(ApplicationError) as exc:
        service.register_return(loan_id=100)

    assert exc.value.status_code == status.HTTP_409_CONFLICT
    assert db.rollbacks == 1
    assert db.commits == 0
    repository.find_copy_for_return.assert_not_called()
    repository.register_return.assert_not_called()

def test_service_trata_falha_de_banco_na_devolucao():
    from sqlalchemy.exc import SQLAlchemyError

    class DatabaseError(SQLAlchemyError):
        pass

    repository = MagicMock()
    db = FakeSession()
    client_service = MagicMock()

    repository.find_loan_for_return.return_value = _open_loan()
    repository.find_copy_for_return.return_value = _borrowed_copy()
    repository.register_return.side_effect = DatabaseError(
        "database error"
    )

    service = LoanService(
        repository=repository,
        db=db,
        client_pendency_service=client_service,
    )

    with pytest.raises(ApplicationError) as exc:
        service.register_return(loan_id=100)

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert db.rollbacks == 1
    assert db.commits == 0

class FakeReturnLoanService:
    def __init__(self):
        self.loan_ids = []

    def register_return(self, loan_id: int):
        self.loan_ids.append(loan_id)

        return SimpleNamespace(
            id=loan_id,
            client_id=42,
            copy_id=15,
            employee_id=7,
            loan_date=datetime(
                2026,
                9,
                26,
                14,
                0,
                tzinfo=timezone.utc,
            ),
            due_date=datetime(
                2026,
                10,
                1,
                18,
                0,
                tzinfo=timezone.utc,
            ),
            returned_at=datetime.now(timezone.utc),
            status=LoanStatus.RETURNED,
        )


def test_controller_registra_devolucao():
    from app.controllers.loan_controller import register_return

    service = FakeReturnLoanService()

    response = register_return(
        loan_id=100,
        current_user=SimpleNamespace(id=7),
        loan_service=service,
    )

    assert service.loan_ids == [100]
    assert response.id == 100
    assert response.status == LoanStatus.RETURNED
    assert response.returned_at is not None

@pytest.mark.parametrize(
    "started, expected",
    [
        (datetime(2027, 1, 31, 15, 0, tzinfo=timezone.utc), (2027, 2, 28, 12)),
        (datetime(2028, 1, 31, 15, 0, tzinfo=timezone.utc), (2028, 2, 29, 12)),
        (datetime(2027, 1, 31, 2, 0, tzinfo=timezone.utc), (2027, 2, 28, 23)),  # 30/01 23h em São Paulo
        (datetime(2026, 12, 15, 15, 0, tzinfo=timezone.utc), (2027, 1, 15, 12)),
    ],
)
def test_prazo_unico_um_mes_em_sao_paulo_com_ajuste_de_fim_de_mes(started, expected):
    due = loan_due_at(started).astimezone(BUSINESS_ZONE)
    assert (due.year, due.month, due.day, due.hour) == expected


def test_service_recusa_exemplar_comercial_com_409_copy_not_for_loan():
    repository = MagicMock()
    db = FakeSession()
    copy = _available_copy()
    copy.destination = DestinationType.COMMERCIAL
    repository.find_copy_for_loan.return_value = copy
    service = LoanService(repository=repository, db=db, client_pendency_service=MagicMock())

    with pytest.raises(CopyNotForLoanError) as error:
        service.create_loan(_loan_data(), employee_id=7)

    assert (error.value.status_code, error.value.code) == (409, "copy_not_for_loan")
    repository.create_loan.assert_not_called()
    assert (db.commits, db.rollbacks) == (0, 1)


def test_overdue_cutoff_e_inicio_do_dia_de_sao_paulo():
    cutoff = overdue_cutoff(date(2026, 10, 3))
    assert cutoff == datetime(2026, 10, 3, 3, 0, tzinfo=timezone.utc)
    assert cutoff.astimezone(BUSINESS_ZONE).hour == 0


@pytest.mark.parametrize("cutoff", [
    datetime(2026, 10, 3, 2, 59, tzinfo=timezone.utc),
    datetime(2026, 10, 3, 3, 0, tzinfo=timezone.utc),
])
def test_list_overdue_loans_usa_o_corte_injetado_com_comparacao_estrita(cutoff):
    from sqlalchemy.dialects import postgresql
    from app.repositories.client_pendency_repository import ClientPendencyRepository

    db = MagicMock()
    ClientPendencyRepository(db).list_overdue_loans(1, cutoff=cutoff)
    compiled = db.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    sql = str(compiled)

    assert "loans.due_date < %(due_date_1)s" in sql
    assert compiled.params["due_date_1"] == cutoff
    assert "loans.returned_at IS NULL" in sql
