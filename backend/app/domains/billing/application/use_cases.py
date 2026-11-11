"""Billing use cases: credit-pack checkout, portal, invoices, and
webhook-driven credit grants.

The BillingAccount anchors the org to its Stripe customer; pack and plan
checkouts, the portal, and invoice reads all reuse one customer.
"""

import logging
import uuid

from app.domains.audit.domain import AuditEvent
from app.domains.audit.domain import actions as audit_actions
from app.domains.auth.domain import User
from app.domains.billing.application.dtos import (
    BillingEvent,
    CommunitySubscriptionActivated,
    CommunitySubscriptionEnded,
    CommunitySubscriptionSynced,
    CreditPackPurchased,
    OrgSubscriptionChanged,
)
from app.domains.billing.application.ports import (
    ActivityTracker,
    AuditRecorder,
    BillingAccountRepository,
    CommunityMembershipService,
    CreditService,
    OrgSubscriptionService,
    PaymentGateway,
    PurchaseReceiptMailer,
)
from app.domains.billing.domain import (
    BillingAccount,
    BillingNotConfigured,
    InvoiceSummary,
    NoBillingAccount,
    PackNotPurchasable,
)
from app.domains.credits.domain import CREDIT_PACKS, CreditPack, UnknownCreditPack
from app.domains.organizations.domain import Organization

logger = logging.getLogger(__name__)


class GetOrCreateBillingAccount:
    def __init__(self, accounts: BillingAccountRepository) -> None:
        self.accounts = accounts

    async def execute(self, org_id: uuid.UUID) -> BillingAccount:
        account = await self.accounts.get_for_org(org_id)
        if account is None:
            account = BillingAccount(organization_id=org_id)
            await self.accounts.add(account)
        return account


class CreateCreditPackCheckout:
    """One-time (mode=payment) checkout for a credit pack. The grant itself
    happens when the webhook's `CreditPackPurchased` event lands."""

    def __init__(self, accounts: BillingAccountRepository, gateway: PaymentGateway) -> None:
        self.accounts = accounts
        self.gateway = gateway

    async def execute(self, org: Organization, user: User, pack: CreditPack) -> str:
        if not self.gateway.is_configured():
            raise BillingNotConfigured("Stripe is not configured (STRIPE_SECRET_KEY).")
        if pack not in CREDIT_PACKS:
            raise UnknownCreditPack(f"Credit pack '{pack.value}' is not in the catalog.")
        if not self.gateway.is_pack_purchasable(pack):
            raise PackNotPurchasable(f"Credit pack '{pack.value}' has no Stripe price configured.")

        account = await GetOrCreateBillingAccount(self.accounts).execute(org.id)
        if not account.has_billing_account:
            account.attach_customer(
                await self.gateway.create_customer(
                    email=user.email, name=org.name, org_id=str(org.id)
                )
            )
        return await self.gateway.create_credit_pack_checkout_url(
            customer_id=account.stripe_customer_id,
            pack=pack,
            org_id=str(org.id),
            user_id=str(user.id),
        )


class CreatePortal:
    def __init__(self, accounts: BillingAccountRepository, gateway: PaymentGateway) -> None:
        self.accounts = accounts
        self.gateway = gateway

    async def execute(self, org_id: uuid.UUID) -> str:
        if not self.gateway.is_configured():
            raise BillingNotConfigured("Stripe is not configured (STRIPE_SECRET_KEY).")
        account = await GetOrCreateBillingAccount(self.accounts).execute(org_id)
        if not account.has_billing_account:
            raise NoBillingAccount("This organization has no billing account yet.")
        return await self.gateway.create_portal_url(customer_id=account.stripe_customer_id)


class ListInvoices:
    """Past invoices, read through from the provider (never cached locally).

    Returns [] when billing isn't configured or the org has no billing
    account yet — an org that never bought anything simply has no invoices,
    not an error."""

    def __init__(self, accounts: BillingAccountRepository, gateway: PaymentGateway) -> None:
        self.accounts = accounts
        self.gateway = gateway

    async def execute(self, org_id: uuid.UUID) -> list[InvoiceSummary]:
        if not self.gateway.is_configured():
            return []
        account = await GetOrCreateBillingAccount(self.accounts).execute(org_id)
        if not account.has_billing_account:
            return []
        return await self.gateway.list_invoices(customer_id=account.stripe_customer_id)


class SyncBillingEvent:
    """Apply a neutral webhook event, dispatched by type: credit-pack
    purchases grant credits (idempotently — Stripe delivers at least once)
    and send a best-effort receipt; community subscription events update the
    membership row via the CommunityMembershipService port."""

    def __init__(
        self,
        credits: CreditService | None = None,
        receipts: PurchaseReceiptMailer | None = None,
        audit: AuditRecorder | None = None,
        community: CommunityMembershipService | None = None,
        analytics: ActivityTracker | None = None,
        org_subscriptions: OrgSubscriptionService | None = None,
    ) -> None:
        self.credits = credits
        self.receipts = receipts
        self.audit = audit
        self.community = community
        self.analytics = analytics
        self.org_subscriptions = org_subscriptions

    async def execute(self, event: BillingEvent) -> None:
        if isinstance(event, OrgSubscriptionChanged):
            if self.org_subscriptions is not None:
                await self.org_subscriptions.execute(event)
            else:
                logger.warning("Org subscription event received without a handler")
        elif isinstance(event, CreditPackPurchased):
            await self._apply_credit_pack(event)
        elif isinstance(
            event,
            (
                CommunitySubscriptionActivated,
                CommunitySubscriptionSynced,
                CommunitySubscriptionEnded,
            ),
        ):
            await self._apply_community(event)
        else:  # pragma: no cover — parse_event only emits the types above
            logger.warning("unhandled billing event type %s", type(event).__name__)

    async def _apply_community(
        self,
        event: (
            CommunitySubscriptionActivated
            | CommunitySubscriptionSynced
            | CommunitySubscriptionEnded
        ),
    ) -> None:
        if self.community is None:
            logger.warning(
                "community subscription event received but no community service is wired"
            )
            return
        if isinstance(event, CommunitySubscriptionActivated):
            await self.community.activate(
                user_id=event.user_id,
                stripe_customer_id=event.stripe_customer_id,
                subscription_id=event.subscription_id,
            )
        elif isinstance(event, CommunitySubscriptionSynced):
            await self.community.sync(
                subscription_id=event.subscription_id,
                status=event.status,
                current_period_end=event.current_period_end,
                cancel_at_period_end=event.cancel_at_period_end,
                user_id=event.user_id,
            )
        else:
            await self.community.end(subscription_id=event.subscription_id)

    async def _apply_credit_pack(self, event: CreditPackPurchased) -> None:
        if self.credits is None:
            logger.warning(
                "Credit pack purchase %s received but no credit service is wired",
                event.session_id,
            )
            return
        if await self.credits.already_granted(event.session_id):
            return  # webhook redelivery — already credited
        await self.credits.grant(
            event.org_id,
            event.credits,
            f"Credit pack purchased: {event.pack_name} (+{event.credits})",
            idempotency_key=event.session_id,
        )
        # Inside the non-redelivery path, so redeliveries don't double-log.
        # No authenticated actor in the webhook context — the purchaser is
        # identified by email in meta.
        if self.audit:
            await self.audit.record(
                AuditEvent(
                    action=audit_actions.CREDIT_PACK_PURCHASED,
                    organization_id=event.org_id,
                    meta={
                        "pack": event.pack_name,
                        "credits": event.credits,
                        "session_id": event.session_id,
                        "purchaser_email": event.purchaser_email,
                    },
                )
            )
        # Revenue truth for product analytics — same non-redelivery path, and
        # in the grant's transaction, so it is exactly-once with the credits.
        if self.analytics:
            await self.analytics.capture_server_event(
                event.user_id,
                "credit_pack_purchased",
                {
                    "pack": event.pack,
                    "credits": event.credits,
                    "amount_cents": event.amount_cents,
                },
            )
        if event.purchaser_email and self.receipts:
            await self.receipts.send_credit_pack_receipt(
                event.purchaser_email, event.pack_name, event.credits
            )
