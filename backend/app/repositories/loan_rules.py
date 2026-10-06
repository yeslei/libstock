from datetime import datetime

from sqlalchemy import and_

from app.models.domain import Loan, LoanStatus


def overdue_open_loan_clause(cutoff: datetime, loan=Loan):
    """Single overdue predicate shared by circulation flows."""
    return and_(
        loan.status == LoanStatus.OPEN,
        loan.returned_at.is_(None),
        loan.due_date < cutoff,
    )
