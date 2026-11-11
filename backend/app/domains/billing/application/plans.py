"""Organization subscriptions: reads, checkout, and Stripe-authoritative updates."""

import logging
import uuid
from datetime import UTC, datetime

from app.core.policy import BILLING_PLAN_GRACE_DAYS, BILLING_TRIAL_DAYS
from app.domains.audit.domain import AuditEvent
from app.domains.audit.domain import actions as audit_actions
from app.domains.auth.domain import User
from app.domains.billing.application.dtos import (
    OrgSubscriptionChanged,
    PlanCatalogRow,
    PlanOverview,
)
from app.domains.billing.application.ports import (
    ActivityTracker,
    AuditRecorder,
    BillingAccountRepository,
    CreditService,
    OrganizationReader,
    PaymentGateway,
    SubscriptionRepository,
)
from app.domains.billing.application.use_cases import GetOrCreateBillingAccount
from app.domains.billing.domain.entities import Subscription
from app.domains.billing.domain.errors import PlanNotConfigured, SubscriptionAlreadyActive
from app.domains.billing.domain.value_objects import (
    PLANS,
    BillingInterval,
    Plan,
    PlanSubscriptionStatus,
)
from app.domains.credits.domain import MONTHLY_ALLOWANCE_CREDITS
from app.domains.organizations.domain import Organization

logger = logging.getLogger(__name__)
LIVE_STATUSES = (
    PlanSubscriptionStatus.TRIALING,
    PlanSubscriptionStatus.ACTIVE,
    PlanSubscriptionStatus.PAST_DUE,
)


class PlanReader:
    def __init__(self, subscriptions: SubscriptionRepository) -> None:
        self.subscriptions = subscriptions

    async def subscription_for(self, org_id: uuid.UUID) -> Subscription | None:
        return await self.subscriptions.get_for_org(org_id)

    async def overview(self, org_id: uuid.UUID) -> PlanOverview:
        subscription = await self.subscription_for(org_id)
        return PlanOverview(
            plan=(
                subscription.effective_plan(grace_days=BILLING_PLAN_GRACE_DAYS)
                if subscription
                else Plan.FREE
            ),
            subscription=subscription,
        )

    async def plan_for(self, org_id: uuid.UUID) -> Plan:
        return (await self.overview(org_id)).plan

    async def monthly_allowance_for(self, org_id: uuid.UUID) -> int | None:
        return PLANS[await self.plan_for(org_id)].monthly_credits


class ListPlans:
    def __init__(self, gateway: PaymentGateway) -> None:
        self.gateway = gateway

    def execute(self) -> list[PlanCatalogRow]:
        return [
            PlanCatalogRow(
                plan=spec.plan,
                name=spec.name,
                monthly_price_cents=spec.monthly_price_cents,
                annual_price_cents=spec.annual_price_cents,
                monthly_credits=(
                    MONTHLY_ALLOWANCE_CREDITS
                    if spec.monthly_credits is None
                    else spec.monthly_credits
                ),
                purchasable={
                    interval.value: spec.plan != Plan.FREE
                    and self.gateway.is_configured()
                    and self.gateway.is_plan_purchasable(spec.plan, interval)
                    for interval in BillingInterval
                },
            )
            for spec in PLANS.values()
        ]


class CreatePlanCheckout:
    def __init__(
        self,
        accounts: BillingAccountRepository,
        subscriptions: SubscriptionRepository,
        gateway: PaymentGateway,
    ) -> None:
        self.accounts = accounts
        self.subscriptions = subscriptions
        self.gateway = gateway

    async def execute(
        self,
        org: Organization,
        user: User,
        plan: Plan,
        interval: BillingInterval,
    ) -> str:
        # The HTTP schema rejects free before the application is called.
        if (
            plan == Plan.FREE
            or not self.gateway.is_configured()
            or not (self.gateway.is_plan_purchasable(plan, interval))
        ):
            raise PlanNotConfigured()
        subscription = await self.subscriptions.get_for_org(org.id)
        if subscription and subscription.status in LIVE_STATUSES:
            raise SubscriptionAlreadyActive()
        account = await GetOrCreateBillingAccount(self.accounts).execute(org.id)
        if not account.has_billing_account:
            account.attach_customer(
                await self.gateway.create_customer(
                    email=user.email,
                    name=org.name,
                    org_id=str(org.id),
                )
            )
        return await self.gateway.create_plan_checkout_url(
            customer_id=account.stripe_customer_id,
            plan=plan,
            interval=interval,
            org_id=str(org.id),
            user_id=str(user.id),
            trial_days=BILLING_TRIAL_DAYS,
        )


class ApplyOrgSubscriptionEvent:
    def __init__(
        self,
        subscriptions: SubscriptionRepository,
        organizations: OrganizationReader,
        gateway: PaymentGateway,
        credits: CreditService | None = None,
        audit: AuditRecorder | None = None,
        analytics: ActivityTracker | None = None,
    ) -> None:
        self.subscriptions = subscriptions
        self.organizations = organizations
        self.gateway = gateway
        self.credits = credits
        self.audit = audit
        self.analytics = analytics

    async def execute(self, event: OrgSubscriptionChanged) -> None:
        snapshot = await self.gateway.fetch_subscription(event.subscription_id)
        if snapshot is None or not snapshot.is_org_plan:
            logger.warning("Missing or untagged org subscription %s", event.subscription_id)
            return
        org_id = snapshot.org_id or event.org_id
        if not isinstance(org_id, uuid.UUID) or await self.organizations.get(org_id) is None:
            logger.warning("Unknown organization for subscription %s", event.subscription_id)
            return
        row = await self.subscriptions.get_for_org_locked(org_id)
        # A concurrent delivery may have waited with an older fetched snapshot.
        # Read again under the transaction lock so it cannot undo the winner.
        snapshot = await self.gateway.fetch_subscription(event.subscription_id)
        if (
            snapshot is None
            or not snapshot.is_org_plan
            or (snapshot.org_id is not None and snapshot.org_id != org_id)
        ):
            logger.warning("Subscription changed identity while locking %s", event.subscription_id)
            return
        live = snapshot.status in LIVE_STATUSES
        recognized = snapshot.plan is not None and snapshot.interval is not None
        if row and row.stripe_subscription_id != snapshot.subscription_id and not live:
            return
        now = datetime.now(UTC)
        previous = row.plan if row and row.status in LIVE_STATUSES else Plan.FREE
        previous_interval = row.interval if row else None
        previous_effective = (
            row.effective_plan(grace_days=BILLING_PLAN_GRACE_DAYS, now=now) if row else Plan.FREE
        )
        if row is None:
            if not live or not recognized:
                logger.warning(
                    "Ignoring non-live or unknown-price subscription %s", snapshot.subscription_id
                )
                return
            row = Subscription(
                organization_id=org_id,
                stripe_subscription_id=snapshot.subscription_id,
                plan=snapshot.plan,
                interval=snapshot.interval,
                status=snapshot.status,
            )
            await self.subscriptions.add(row)
        if not recognized:
            logger.warning(
                "Keeping existing plan for unknown price on %s", snapshot.subscription_id
            )
        row.apply(
            stripe_subscription_id=snapshot.subscription_id,
            plan=snapshot.plan if recognized else row.plan,
            interval=snapshot.interval if recognized else row.interval,
            status=snapshot.status,
            current_period_end=snapshot.current_period_end,
            cancel_at_period_end=snapshot.cancel_at_period_end,
        )
        # Credits follow time-aware access, independently of lifecycle reporting.
        # Recovery after grace lapse can restore an allowance without a new sale.
        current_effective = row.effective_plan(grace_days=BILLING_PLAN_GRACE_DAYS, now=now)
        old_allowance = PLANS[previous_effective].monthly_credits
        new_allowance = PLANS[current_effective].monthly_credits
        if (
            self.credits
            and previous_effective != current_effective
            and current_effective != Plan.FREE
            and (previous_effective == Plan.FREE or (new_allowance or 0) > (old_allowance or 0))
        ):
            await self.credits.top_up_plan_allowance(
                org_id,
                previous_allowance=(
                    MONTHLY_ALLOWANCE_CREDITS if old_allowance is None else old_allowance
                ),
                new_allowance=(
                    MONTHLY_ALLOWANCE_CREDITS if new_allowance is None else new_allowance
                ),
                idempotency_key=f"plan-topup:{org_id}:{now:%Y-%m}:{current_effective.value}",
            )

        # Lifecycle transitions follow provider status, never the grace clock.
        # Interval-only changes count while paid; duplicate deliveries stay silent.
        current = row.plan if row.status in LIVE_STATUSES else Plan.FREE
        if previous == current and (current == Plan.FREE or previous_interval == row.interval):
            return
        properties = {
            "plan": current.value,
            "interval": row.interval.value,
            "previous_plan": previous.value,
            "subscription_id": row.stripe_subscription_id,
        }
        analytics_properties = {"organization_id": str(org_id)}
        if current == Plan.FREE:
            action, event_name = audit_actions.PLAN_CANCELED, "plan_canceled"
            analytics_properties["plan"] = previous.value
        else:
            analytics_properties.update(plan=current.value, interval=row.interval.value)
            if previous == Plan.FREE:
                action, event_name = audit_actions.PLAN_SUBSCRIBED, "plan_subscribed"
            else:
                action, event_name = audit_actions.PLAN_CHANGED, "plan_changed"
        if self.audit:
            await self.audit.record(
                AuditEvent(
                    action=action,
                    organization_id=org_id,
                    meta=properties,
                )
            )
        if self.analytics and snapshot.user_id is not None:
            await self.analytics.capture_server_event(
                snapshot.user_id, event_name, analytics_properties
            )
