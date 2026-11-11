"""Stripe gateway — implements the PaymentGateway port.

This is the anti-corruption layer: Stripe's wire format (nested event dicts,
price ids, epoch timestamps) is translated into domain values here and goes
no further. The Stripe SDK is synchronous, so every call is pushed to a
worker thread to keep the event loop free.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import stripe

from app.core.config import settings
from app.domains.billing.application.dtos import (
    BillingEvent,
    CommunitySubscriptionActivated,
    CommunitySubscriptionEnded,
    CommunitySubscriptionSynced,
    CreditPackPurchased,
    OrgSubscriptionChanged,
    SubscriptionSnapshot,
)
from app.domains.billing.domain import InvoiceSummary, StripeUnavailable
from app.domains.billing.domain.value_objects import (
    PAID_PLANS,
    BillingInterval,
    Plan,
    PlanSubscriptionStatus,
)
from app.domains.community.domain import CommunityPlan, SubscriptionStatus
from app.domains.credits.domain import CREDIT_PACKS, CreditPack

logger = logging.getLogger("app.errors")


async def _stripe_call(fn, /, *args, **kwargs):
    """Run a Stripe SDK call in a worker thread, mapping infrastructure
    failures (connection errors, Stripe 5xx, rate limits) to StripeUnavailable
    (ERR_BILL_002 — "you have not been charged"). Card/validation errors are
    NOT caught here: they mean Stripe was reached and answered.
    """
    try:
        return await asyncio.to_thread(fn, *args, **kwargs)
    except (stripe.APIConnectionError, stripe.RateLimitError, stripe.APIError) as exc:
        request_id = getattr(exc, "request_id", None)
        logger.error("stripe unavailable: %s (stripe-request-id=%s)", exc, request_id)
        raise StripeUnavailable() from exc


def _as_dict(obj: Any) -> Any:
    """Normalize an SDK object to a plain dict at the boundary. stripe>=15
    objects are not dicts — indexing works but `.get()` raises — so the
    translators below would break on real provider payloads otherwise."""
    to_dict = getattr(obj, "_to_dict_recursive", None)
    return to_dict() if callable(to_dict) else obj


def _uuid_or_none(raw: object) -> uuid.UUID | None:
    """Metadata is free-form at Stripe — never let a malformed id sink a webhook."""
    try:
        return uuid.UUID(str(raw)) if raw else None
    except ValueError:
        return None


def _credit_pack_price_id(pack: CreditPack) -> str:
    # Settings fields follow the enum: stripe_price_credits_<pack value>, so
    # adding a pack never requires touching this function.
    return getattr(settings, f"stripe_price_credits_{pack.value}", "")


def _community_price_id(plan: CommunityPlan) -> str:
    # Settings fields follow the enum: stripe_price_community_<plan value>.
    return getattr(settings, f"stripe_price_community_{plan.value}", "")


def _plan_price_id(plan: Plan, interval: BillingInterval) -> str:
    return getattr(settings, f"stripe_price_plan_{plan.value}_{interval.value}", "")


def _plan_subscription_status(raw: str) -> PlanSubscriptionStatus:
    try:
        return PlanSubscriptionStatus(raw)
    except ValueError:
        return PlanSubscriptionStatus.CANCELED


def _subscription_status(stripe_status: str) -> SubscriptionStatus:
    """Stripe's subscription lifecycle → the three states the domain cares
    about. trialing counts as active; unpaid as past_due; everything else
    (canceled, incomplete_expired, paused, …) as canceled."""
    if stripe_status in ("active", "trialing"):
        return SubscriptionStatus.ACTIVE
    if stripe_status in ("past_due", "unpaid"):
        return SubscriptionStatus.PAST_DUE
    return SubscriptionStatus.CANCELED


def _period_end(sub: dict) -> datetime | None:
    """Paid-through timestamp. On the 2025 "basil" API current_period_end
    lives on the subscription items; older payloads have it top-level."""
    epoch = sub.get("current_period_end")
    if epoch is None:
        items = ((sub.get("items") or {}).get("data")) or []
        if items:
            epoch = items[0].get("current_period_end")
    return datetime.fromtimestamp(epoch, tz=UTC) if epoch else None


def _is_community_tagged(obj: dict) -> bool:
    return (obj.get("metadata") or {}).get("community_membership") == "1"


def _to_invoice(stripe_inv: Any) -> InvoiceSummary:
    """Stripe invoice object → provider-neutral summary."""
    return InvoiceSummary(
        id=stripe_inv["id"],
        number=stripe_inv.get("number"),
        status=stripe_inv["status"],
        amount_due=stripe_inv["amount_due"],
        currency=stripe_inv["currency"],
        created=datetime.fromtimestamp(stripe_inv["created"], tz=UTC),
        hosted_invoice_url=stripe_inv.get("hosted_invoice_url"),
        invoice_pdf=stripe_inv.get("invoice_pdf"),
    )


class StripeGateway:
    def __init__(self) -> None:
        stripe.api_key = settings.stripe_secret_key

    def is_configured(self) -> bool:
        return bool(settings.stripe_secret_key)

    def is_pack_purchasable(self, pack: CreditPack) -> bool:
        return bool(_credit_pack_price_id(pack))

    def is_community_plan_purchasable(self, plan: CommunityPlan) -> bool:
        return bool(_community_price_id(plan))

    def is_plan_purchasable(self, plan: Plan, interval: BillingInterval) -> bool:
        return plan in PAID_PLANS and self.is_configured() and bool(_plan_price_id(plan, interval))

    async def create_plan_checkout_url(
        self,
        *,
        customer_id: str,
        plan: Plan,
        interval: BillingInterval,
        org_id: str,
        user_id: str,
        trial_days: int,
    ) -> str:
        metadata = {
            "org_plan": "1",
            "organization_id": org_id,
            "plan": plan.value,
            "interval": interval.value,
            "user_id": user_id,
        }
        subscription_data = {"metadata": metadata}
        if trial_days > 0:
            subscription_data["trial_period_days"] = trial_days
        session = await _stripe_call(
            stripe.checkout.Session.create,
            mode="subscription",
            customer=customer_id,
            client_reference_id=org_id,
            allow_promotion_codes=True,
            line_items=[{"price": _plan_price_id(plan, interval), "quantity": 1}],
            success_url=f"{settings.frontend_url}/billing?status=success",
            cancel_url=f"{settings.frontend_url}/billing?status=canceled",
            metadata=metadata,
            subscription_data=subscription_data,
        )
        return session["url"]

    async def fetch_subscription(self, subscription_id: str) -> SubscriptionSnapshot | None:
        try:
            sub = _as_dict(await _stripe_call(stripe.Subscription.retrieve, subscription_id))
        except stripe.InvalidRequestError as exc:
            if exc.code == "resource_missing" or exc.http_status == 404:
                return None
            raise
        metadata = sub.get("metadata") or {}
        items = (sub.get("items") or {}).get("data") or []
        price = (items[0].get("price") or {}) if items else {}
        price_id = price if isinstance(price, str) else price.get("id")
        plan, interval = next(
            (
                (plan, interval)
                for plan in PAID_PLANS
                for interval in BillingInterval
                if price_id and _plan_price_id(plan, interval) == price_id
            ),
            (None, None),
        )
        return SubscriptionSnapshot(
            subscription_id=sub["id"],
            org_id=_uuid_or_none(metadata.get("organization_id")),
            user_id=_uuid_or_none(metadata.get("user_id")),
            plan=plan,
            interval=interval,
            status=_plan_subscription_status(sub.get("status", "")),
            current_period_end=_period_end(sub),
            cancel_at_period_end=bool(sub.get("cancel_at_period_end")),
            is_org_plan=metadata.get("org_plan") == "1" and not _is_community_tagged(sub),
        )

    async def list_org_plan_subscriptions(self) -> list[SubscriptionSnapshot]:
        """Page all statuses and reuse fetch_subscription's authoritative mapping."""
        snapshots = []
        params = {"status": "all", "limit": 100}
        while True:
            page = _as_dict(await _stripe_call(stripe.Subscription.list, **params))
            for sub in page["data"]:
                if (sub.get("metadata") or {}).get("org_plan") == "1" and not _is_community_tagged(
                    sub
                ):
                    snapshot = await self.fetch_subscription(sub["id"])
                    if snapshot is not None and snapshot.is_org_plan:
                        snapshots.append(snapshot)
            if not page.get("has_more"):
                return snapshots
            params["starting_after"] = page["data"][-1]["id"]

    async def create_customer(self, *, email: str, name: str, org_id: str) -> str:
        customer = await _stripe_call(
            stripe.Customer.create, email=email, name=name, metadata={"organization_id": org_id}
        )
        return customer["id"]

    async def create_customer_for_user(self, *, email: str, name: str, user_id: str) -> str:
        """User-level customer for community memberships — deliberately NOT
        the org-shaped create_customer; a person may hold both."""
        customer = await _stripe_call(
            stripe.Customer.create, email=email, name=name, metadata={"user_id": user_id}
        )
        return customer["id"]

    async def create_community_subscription_checkout_url(
        self, *, customer_id: str, plan: CommunityPlan, user_id: str
    ) -> str:
        """Recurring (mode=subscription) checkout for a community membership.
        Both the session AND the subscription carry the community tag +
        user_id, so every later subscription webhook can self-identify."""
        session = await _stripe_call(
            stripe.checkout.Session.create,
            mode="subscription",
            customer=customer_id,
            client_reference_id=user_id,
            allow_promotion_codes=True,
            line_items=[{"price": _community_price_id(plan), "quantity": 1}],
            success_url=f"{settings.frontend_url}/community?status=success",
            cancel_url=f"{settings.frontend_url}/community/upgrade?status=canceled",
            metadata={"community_membership": "1", "user_id": user_id},
            subscription_data={"metadata": {"community_membership": "1", "user_id": user_id}},
        )
        return session["url"]

    async def create_credit_pack_checkout_url(
        self, *, customer_id: str, pack: CreditPack, org_id: str, user_id: str | None = None
    ) -> str:
        """One-time payment checkout for a credit pack. The metadata is what
        `parse_event` later uses to recognize and route the completion;
        `user_id` (the member who clicked buy) attributes the purchase in
        product analytics — the grant itself is org-level."""
        metadata = {"organization_id": org_id, "credit_pack": pack.value}
        if user_id:
            metadata["user_id"] = user_id
        session = await _stripe_call(
            stripe.checkout.Session.create,
            mode="payment",
            customer=customer_id,
            client_reference_id=org_id,
            allow_promotion_codes=True,
            line_items=[{"price": _credit_pack_price_id(pack), "quantity": 1}],
            success_url=f"{settings.frontend_url}/billing?status=success",
            cancel_url=f"{settings.frontend_url}/billing?status=canceled",
            metadata=metadata,
        )
        return session["url"]

    async def create_portal_url(self, *, customer_id: str) -> str:
        session = await _stripe_call(
            stripe.billing_portal.Session.create,
            customer=customer_id,
            return_url=f"{settings.frontend_url}/billing",
        )
        return session["url"]

    async def list_invoices(self, *, customer_id: str, limit: int = 12) -> list[InvoiceSummary]:
        invoices = await _stripe_call(stripe.Invoice.list, customer=customer_id, limit=limit)
        return [_to_invoice(_as_dict(inv)) for inv in invoices["data"]]

    def verify_webhook(self, payload: bytes, signature: str) -> dict:
        """Raises ValueError / stripe.SignatureVerificationError on bad input."""
        if not settings.stripe_webhook_secret:
            # An empty secret is a key every attacker knows: construct_event
            # would happily verify a signature computed with "". Refuse in
            # every environment — for local testing `stripe listen` prints a
            # real whsec_ to put in .env.
            raise ValueError("STRIPE_WEBHOOK_SECRET is not set; refusing webhook.")
        event = stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
        return _as_dict(event)

    async def parse_event(self, event: dict) -> BillingEvent | None:
        etype = event["type"]
        obj = event["data"]["object"]
        # Community tags retain precedence, including malformed dual-tagged
        # objects: no object can dispatch into both subscription systems.
        if (obj.get("metadata") or {}).get("org_plan") == "1" and not _is_community_tagged(obj):
            subscription_id = None
            if etype == "checkout.session.completed" and obj.get("mode") == "subscription":
                subscription_id = obj.get("subscription")
            elif etype in (
                "customer.subscription.created",
                "customer.subscription.updated",
                "customer.subscription.deleted",
            ):
                subscription_id = obj.get("id")
            if subscription_id:
                return OrgSubscriptionChanged(
                    subscription_id=subscription_id,
                    org_id=_uuid_or_none((obj.get("metadata") or {}).get("organization_id")),
                )
            return None
        if etype == "checkout.session.completed":
            if obj.get("mode") == "payment":
                return self._parse_credit_pack_completed(obj)
            if obj.get("mode") == "subscription" and _is_community_tagged(obj):
                return self._parse_community_activated(obj)
            return None
        if etype in ("customer.subscription.created", "customer.subscription.updated"):
            if not _is_community_tagged(obj):
                return None
            return self._parse_community_synced(obj)
        if etype == "customer.subscription.deleted":
            if not _is_community_tagged(obj):
                return None
            return CommunitySubscriptionEnded(subscription_id=obj["id"])
        return None

    def _parse_credit_pack_completed(self, obj: dict) -> CreditPackPurchased | None:
        org_id = obj.get("client_reference_id")
        pack_value = (obj.get("metadata") or {}).get("credit_pack")
        if not (org_id and pack_value):
            return None
        try:
            spec = CREDIT_PACKS[CreditPack(pack_value)]
        except (ValueError, KeyError):
            logger.warning("checkout completed for unknown credit pack %r", pack_value)
            return None
        return CreditPackPurchased(
            org_id=uuid.UUID(org_id),
            pack_name=spec.name,
            credits=spec.credits,
            session_id=obj["id"],
            purchaser_email=(obj.get("customer_details") or {}).get("email"),
            user_id=_uuid_or_none((obj.get("metadata") or {}).get("user_id")),
            pack=spec.pack.value,
            amount_cents=spec.price_cents,
        )

    def _parse_community_activated(self, obj: dict) -> CommunitySubscriptionActivated | None:
        user_id = (obj.get("metadata") or {}).get("user_id")
        if not (user_id and obj.get("customer") and obj.get("subscription")):
            logger.warning("community checkout session %s missing fields", obj.get("id"))
            return None
        return CommunitySubscriptionActivated(
            user_id=uuid.UUID(user_id),
            stripe_customer_id=obj["customer"],
            subscription_id=obj["subscription"],
            purchaser_email=(obj.get("customer_details") or {}).get("email"),
        )

    def _parse_community_synced(self, sub: dict) -> CommunitySubscriptionSynced:
        raw_user_id = (sub.get("metadata") or {}).get("user_id")
        return CommunitySubscriptionSynced(
            subscription_id=sub["id"],
            status=_subscription_status(sub.get("status", "")),
            current_period_end=_period_end(sub),
            cancel_at_period_end=bool(sub.get("cancel_at_period_end")),
            user_id=uuid.UUID(raw_user_id) if raw_user_id else None,
        )
