"""Billing application ports."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from app.domains.audit.domain import AuditEvent
from app.domains.billing.application.dtos import (
    BillingEvent,
    OrgSubscriptionChanged,
    SubscriptionSnapshot,
)
from app.domains.billing.domain import BillingAccount, InvoiceSummary
from app.domains.billing.domain.entities import Subscription
from app.domains.billing.domain.value_objects import BillingInterval, Plan
from app.domains.credits.domain import CreditPack
from app.domains.organizations.domain import Organization

if TYPE_CHECKING:
    from app.domains.billing.application.revenue import RevenueGroup, RevenueSubscription


class BillingAccountRepository(Protocol):
    async def get_for_org(self, org_id: uuid.UUID) -> BillingAccount | None: ...

    async def add(self, account: BillingAccount) -> None: ...


class PaymentGateway(Protocol):
    """The payment provider, behind an anti-corruption layer: raw provider
    payloads never cross this boundary — only `BillingEvent` values do."""

    def is_configured(self) -> bool: ...

    def is_pack_purchasable(self, pack: CreditPack) -> bool: ...

    def is_plan_purchasable(self, plan: Plan, interval: BillingInterval) -> bool: ...

    async def create_plan_checkout_url(
        self,
        *,
        customer_id: str,
        plan: Plan,
        interval: BillingInterval,
        org_id: str,
        user_id: str,
        trial_days: int,
    ) -> str: ...

    async def fetch_subscription(self, subscription_id: str) -> SubscriptionSnapshot | None: ...

    async def create_customer(self, *, email: str, name: str, org_id: str) -> str: ...

    async def create_credit_pack_checkout_url(
        self, *, customer_id: str, pack: CreditPack, org_id: str, user_id: str | None = None
    ) -> str: ...

    async def create_portal_url(self, *, customer_id: str) -> str: ...

    async def list_invoices(self, *, customer_id: str, limit: int = 12) -> list[InvoiceSummary]:
        """Most recent invoices for a billing account, newest first."""
        ...

    def verify_webhook(self, payload: bytes, signature: str) -> dict:
        """Verify and decode a webhook request body. Raises on bad signature."""
        ...

    async def parse_event(self, event: dict) -> "BillingEvent | None":
        """Translate a provider event into a neutral BillingEvent (or None
        for event types we ignore)."""
        ...


class CreditService(Protocol):
    """What the webhook sync needs from the credit engine — satisfied
    structurally by `CreditEngine` (cross-slice port idiom)."""

    async def top_up_plan_allowance(
        self,
        org_id: uuid.UUID,
        *,
        previous_allowance: int,
        new_allowance: int,
        idempotency_key: str,
    ) -> int: ...

    async def already_granted(self, idempotency_key: str) -> bool: ...

    async def grant(
        self,
        org_id: uuid.UUID,
        amount: int,
        description: str,
        user_id: uuid.UUID | None = None,
        idempotency_key: str | None = None,
    ) -> object: ...


class CommunityMembershipService(Protocol):
    """What the webhook sync needs from the community slice — satisfied
    structurally by ApplyCommunitySubscriptionEvent (cross-slice port idiom).
    Every method no-ops on unknown ids, which makes the sync idempotent under
    Stripe's at-least-once delivery."""

    async def activate(
        self,
        *,
        user_id: "uuid.UUID",
        stripe_customer_id: str,
        subscription_id: str,
    ) -> None: ...

    async def sync(
        self,
        *,
        subscription_id: str,
        status: object,
        current_period_end: object,
        cancel_at_period_end: bool,
        user_id: "uuid.UUID | None",
    ) -> None: ...

    async def end(self, *, subscription_id: str) -> None: ...


class PurchaseReceiptMailer(Protocol):
    """Best-effort purchase confirmation — must never raise."""

    async def send_credit_pack_receipt(self, email: str, pack_name: str, credits: int) -> None: ...


class AuditRecorder(Protocol):
    """Security-event trail. Satisfied structurally by the audit slice's
    AutonomousAuditRecorder; writes are best-effort and never raise."""

    async def record(self, event: AuditEvent) -> None: ...


class ActivityTracker(Protocol):
    """Product-analytics server events — satisfied structurally by the
    analytics slice's CaptureServerEvent (cross-slice port idiom). Writes are
    best-effort, never raise, and skip silently when `user_id` is None or the
    user opted out. Event names come from shared/events.toml."""

    async def capture_server_event(
        self, user_id: "uuid.UUID | None", event: str, properties: dict | None = None
    ) -> object: ...


class SubscriptionRepository(Protocol):
    async def get_for_org(self, org_id: uuid.UUID) -> Subscription | None: ...

    async def get_for_org_locked(self, org_id: uuid.UUID) -> Subscription | None:
        """Serialize org subscription updates, including when no row exists yet."""
        ...

    async def get_by_stripe_id(self, subscription_id: str) -> Subscription | None: ...

    async def add(self, subscription: Subscription) -> None: ...


class OrganizationReader(Protocol):
    async def get(self, org_id: uuid.UUID) -> Organization | None: ...


class OrgSubscriptionService(Protocol):
    async def execute(self, event: OrgSubscriptionChanged) -> None: ...


class RevenueReader(Protocol):
    """Platform-wide read model, available only to administrators and operators."""

    async def grouped_revenue(self, now: "datetime") -> list["RevenueGroup"]: ...

    async def list_subscriptions(self) -> list["RevenueSubscription"]: ...


class RevenueGateway(Protocol):
    async def list_org_plan_subscriptions(self) -> list[SubscriptionSnapshot]: ...
