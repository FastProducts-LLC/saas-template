"""Billing composition root."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.analytics.interface.deps import build_activity_tracker
from app.domains.audit.interface.deps import get_audit_recorder
from app.domains.billing.application import use_cases as uc
from app.domains.billing.application.plans import (
    ApplyOrgSubscriptionEvent,
    CreatePlanCheckout,
    ListPlans,
    PlanReader,
)
from app.domains.billing.application.ports import AuditRecorder
from app.domains.billing.application.revenue import GetRevenue, ReconcileRevenue
from app.domains.billing.infrastructure.mailer import BillingReceiptMailer
from app.domains.billing.infrastructure.repositories import (
    SqlAlchemyBillingAccountRepository,
    SqlAlchemySubscriptionRepository,
)
from app.domains.billing.infrastructure.stripe_gateway import StripeGateway
from app.domains.credits.interface.deps import build_credit_engine
from app.domains.organizations.infrastructure.repositories import SqlAlchemyOrgRepository

DB = Annotated[AsyncSession, Depends(get_db)]
Audit = Annotated[AuditRecorder, Depends(get_audit_recorder)]

_gateway = StripeGateway()


def get_payment_gateway() -> StripeGateway:
    return _gateway


def get_billing_account(db: DB) -> uc.GetOrCreateBillingAccount:
    return uc.GetOrCreateBillingAccount(SqlAlchemyBillingAccountRepository(db))


def get_create_credit_pack_checkout(db: DB) -> uc.CreateCreditPackCheckout:
    return uc.CreateCreditPackCheckout(SqlAlchemyBillingAccountRepository(db), _gateway)


def get_create_portal(db: DB) -> uc.CreatePortal:
    return uc.CreatePortal(SqlAlchemyBillingAccountRepository(db), _gateway)


def get_list_invoices(db: DB) -> uc.ListInvoices:
    return uc.ListInvoices(SqlAlchemyBillingAccountRepository(db), _gateway)


def get_sync_billing_event(
    db: DB,
    audit: Audit,
    gateway: Annotated[StripeGateway, Depends(get_payment_gateway)],
) -> uc.SyncBillingEvent:
    # Imported here, not at module top, to avoid a circular import: the
    # community composition root imports get_payment_gateway from this module.
    from app.domains.community.interface.deps import build_community_membership_service

    return uc.SyncBillingEvent(
        credits=build_credit_engine(db),  # credit-pack grants (CreditService port)
        receipts=BillingReceiptMailer(),
        audit=audit,
        community=build_community_membership_service(db),
        analytics=build_activity_tracker(db),
        org_subscriptions=ApplyOrgSubscriptionEvent(
            subscriptions=SqlAlchemySubscriptionRepository(db),
            organizations=SqlAlchemyOrgRepository(db),
            gateway=gateway,
            credits=build_credit_engine(db),
            audit=audit,
            analytics=build_activity_tracker(db),
        ),
    )


def build_plan_reader(db: AsyncSession) -> PlanReader:
    return PlanReader(SqlAlchemySubscriptionRepository(db))


def get_plan_reader(db: DB) -> PlanReader:
    return build_plan_reader(db)


def get_create_plan_checkout(db: DB) -> CreatePlanCheckout:
    return CreatePlanCheckout(
        SqlAlchemyBillingAccountRepository(db),
        SqlAlchemySubscriptionRepository(db),
        _gateway,
    )


def get_list_plans(gateway: Annotated[StripeGateway, Depends(get_payment_gateway)]) -> ListPlans:
    return ListPlans(gateway)


def get_revenue(db: DB) -> "GetRevenue":
    from app.domains.billing.application.revenue import GetRevenue
    from app.domains.billing.infrastructure.revenue import SqlAlchemyRevenueReader

    return GetRevenue(SqlAlchemyRevenueReader(db))


def build_reconcile_revenue(db: AsyncSession, gateway: StripeGateway) -> "ReconcileRevenue":
    from app.domains.billing.application.revenue import ReconcileRevenue
    from app.domains.billing.infrastructure.revenue import SqlAlchemyRevenueReader

    return ReconcileRevenue(SqlAlchemyRevenueReader(db), gateway)
