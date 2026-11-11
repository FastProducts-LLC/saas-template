"""Billing HTTP endpoints, including the Stripe webhook."""

from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request

from app.domains.auth.interface.deps import CurrentVerifiedUser
from app.domains.billing.application import use_cases as uc
from app.domains.billing.application.plans import CreatePlanCheckout, ListPlans, PlanReader
from app.domains.billing.infrastructure.stripe_gateway import StripeGateway
from app.domains.billing.interface.deps import (
    get_billing_account,
    get_create_credit_pack_checkout,
    get_create_plan_checkout,
    get_create_portal,
    get_list_invoices,
    get_list_plans,
    get_payment_gateway,
    get_plan_reader,
    get_sync_billing_event,
)
from app.domains.billing.interface.schemas import (
    BillingAccountOut,
    BillingPlanOut,
    CreditPackCheckoutRequest,
    CreditPackOut,
    InvoiceOut,
    PlanCheckoutRequest,
    PlanOut,
    RedirectResponse,
)
from app.domains.credits.domain import CREDIT_PACKS
from app.domains.organizations.interface.deps import (
    CurrentAdmin,
    CurrentMember,
    OrgQueriesDep,
)

router = APIRouter(tags=["billing"])


@router.get("/orgs/{org_id}/billing", response_model=BillingAccountOut)
async def get_billing(
    membership: CurrentMember,
    use_case: Annotated[uc.GetOrCreateBillingAccount, Depends(get_billing_account)],
):
    account = await use_case.execute(membership.organization_id)
    return BillingAccountOut(has_billing_account=account.has_billing_account)


@router.get("/orgs/{org_id}/billing/invoices", response_model=list[InvoiceOut])
async def list_invoices(
    membership: CurrentAdmin,  # invoice amounts/PDFs are admin-only
    use_case: Annotated[uc.ListInvoices, Depends(get_list_invoices)],
):
    invoices = await use_case.execute(membership.organization_id)
    return [
        InvoiceOut(
            id=inv.id,
            number=inv.number,
            status=inv.status,
            amount_due=inv.amount_due,
            currency=inv.currency,
            created=inv.created,
            hosted_invoice_url=inv.hosted_invoice_url,
            invoice_pdf=inv.invoice_pdf,
        )
        for inv in invoices
    ]


@router.get("/billing/credits/packs", response_model=list[CreditPackOut])
async def list_credit_packs(
    gateway: Annotated[StripeGateway, Depends(get_payment_gateway)],
):
    return [
        CreditPackOut(
            pack=spec.pack,
            name=spec.name,
            credits=spec.credits,
            price_cents=spec.price_cents,
            unit_price_cents=spec.unit_price_cents,
            discount_pct=spec.discount_pct,
            purchasable=gateway.is_configured() and gateway.is_pack_purchasable(spec.pack),
        )
        for spec in CREDIT_PACKS.values()
    ]


@router.post("/orgs/{org_id}/billing/credits/checkout", response_model=RedirectResponse)
async def create_credit_pack_checkout(
    payload: CreditPackCheckoutRequest,
    membership: CurrentAdmin,
    user: CurrentVerifiedUser,
    queries: OrgQueriesDep,
    use_case: Annotated[uc.CreateCreditPackCheckout, Depends(get_create_credit_pack_checkout)],
):
    org = await queries.get_org(membership.organization_id)
    url = await use_case.execute(org, user, payload.pack)
    return RedirectResponse(url=url)


@router.post("/orgs/{org_id}/billing/portal", response_model=RedirectResponse)
async def create_portal(
    membership: CurrentAdmin,
    _user: CurrentVerifiedUser,
    use_case: Annotated[uc.CreatePortal, Depends(get_create_portal)],
):
    url = await use_case.execute(membership.organization_id)
    return RedirectResponse(url=url)


@router.post("/billing/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    gateway: Annotated[StripeGateway, Depends(get_payment_gateway)],
    use_case: Annotated[uc.SyncBillingEvent, Depends(get_sync_billing_event)],
):
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = gateway.verify_webhook(payload, signature)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid Stripe signature.")
    billing_event = await gateway.parse_event(event)
    if billing_event is not None:
        await use_case.execute(billing_event)
    return {"received": True}


@router.get("/billing/plans", response_model=list[PlanOut])
async def list_plans(query: Annotated[ListPlans, Depends(get_list_plans)]):
    return [PlanOut.model_validate(row, from_attributes=True) for row in query.execute()]


@router.get("/orgs/{org_id}/billing/plan", response_model=BillingPlanOut)
async def get_billing_plan(
    membership: CurrentMember,
    reader: Annotated[PlanReader, Depends(get_plan_reader)],
):
    overview = await reader.overview(membership.organization_id)
    return BillingPlanOut.model_validate(overview, from_attributes=True)


@router.post("/orgs/{org_id}/billing/plan/checkout", response_model=RedirectResponse)
async def create_plan_checkout(
    payload: PlanCheckoutRequest,
    membership: CurrentAdmin,
    user: CurrentVerifiedUser,
    queries: OrgQueriesDep,
    use_case: Annotated[CreatePlanCheckout, Depends(get_create_plan_checkout)],
):
    org = await queries.get_org(membership.organization_id)
    url = await use_case.execute(org, user, payload.plan, payload.interval)
    return RedirectResponse(url=url)
