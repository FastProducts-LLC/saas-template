import { api } from "../../../shared/api";
import type { BillingPlan, BillingAccount, CreditPack, CreditPackSpec, Invoice } from "../model/types";

export const listPacks = () => api<CreditPackSpec[]>("/billing/credits/packs");

export const getBillingAccount = (orgId: string) =>
  api<BillingAccount>(`/orgs/${orgId}/billing`);

export const listInvoices = (orgId: string) => api<Invoice[]>(`/orgs/${orgId}/billing/invoices`);

/** Returns a Stripe Checkout URL to open in the system browser. */
export const checkoutPack = (orgId: string, pack: CreditPack) =>
  api<{ url: string }>(`/orgs/${orgId}/billing/credits/checkout`, {
    method: "POST",
    body: JSON.stringify({ pack }),
  });

/** Returns a Stripe customer-portal URL to open in the system browser. */
export const openPortal = (orgId: string) =>
  api<{ url: string }>(`/orgs/${orgId}/billing/portal`, { method: "POST" });

export const getBillingPlan = (orgId: string) =>
  api<BillingPlan>(`/orgs/${orgId}/billing/plan`);
