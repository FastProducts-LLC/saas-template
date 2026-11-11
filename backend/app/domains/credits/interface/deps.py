"""Credits composition root.

`build_credit_engine` is the cross-slice/worker entry point (generations
builds an engine inside its own session); `get_credit_engine` is the
FastAPI dependency.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.credits.application.queries import CreditUsageQueries
from app.domains.credits.application.use_cases import (
    ClearMemberCreditLimit,
    CreditEngine,
    ListMemberCreditLimits,
    SetMemberCreditLimit,
)
from app.domains.credits.infrastructure.mailer import CreditsMailer
from app.domains.credits.infrastructure.repositories import (
    SqlAlchemyLedgerRepository,
    SqlAlchemyMemberLimitRepository,
    SqlAlchemyOrgOwnerEmails,
    SqlAlchemyReservationRepository,
    SqlAlchemyUsageRepository,
    SqlAlchemyWalletRepository,
)
from app.domains.organizations.infrastructure.repositories import SqlAlchemyOrgRepository

DB = Annotated[AsyncSession, Depends(get_db)]


def build_credit_engine(db: AsyncSession) -> CreditEngine:
    from app.domains.billing.interface.deps import build_plan_reader

    return CreditEngine(
        wallets=SqlAlchemyWalletRepository(db),
        reservations=SqlAlchemyReservationRepository(db),
        ledger=SqlAlchemyLedgerRepository(db),
        notifier=CreditsMailer(),
        owners=SqlAlchemyOrgOwnerEmails(db),
        limits=SqlAlchemyMemberLimitRepository(db),
        plan_allowance_reader=build_plan_reader(db),
    )


def get_credit_engine(db: DB) -> CreditEngine:
    return build_credit_engine(db)


def get_set_member_limit(db: DB) -> SetMemberCreditLimit:
    return SetMemberCreditLimit(SqlAlchemyMemberLimitRepository(db), SqlAlchemyOrgRepository(db))


def get_clear_member_limit(db: DB) -> ClearMemberCreditLimit:
    return ClearMemberCreditLimit(SqlAlchemyMemberLimitRepository(db))


def get_list_member_limits(db: DB) -> ListMemberCreditLimits:
    return ListMemberCreditLimits(SqlAlchemyMemberLimitRepository(db))


def get_usage_queries(db: DB) -> CreditUsageQueries:
    return CreditUsageQueries(SqlAlchemyUsageRepository(db), SqlAlchemyMemberLimitRepository(db))
