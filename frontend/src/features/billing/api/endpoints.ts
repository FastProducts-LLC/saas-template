import { api } from "../../../shared/api";

import type { BillingAccount, Invoice, PlanSpec, BillingPlan, PlanCheckout } from "../model/types";

export const getBillingAccount = (orgId: string) => api<BillingAccount>(`/orgs/${orgId}/billing`);

export const listInvoices = (orgId: string) => api<Invoice[]>(`/orgs/${orgId}/billing/invoices`);

export const createPortal = (orgId: string) =>
  api<{ url: string }>(`/orgs/${orgId}/billing/portal`, { method: "POST" });

export const listPlans = () => api<PlanSpec[]>("/billing/plans");
export const getBillingPlan = (orgId: string) => api<BillingPlan>(`/orgs/${orgId}/billing/plan`);
export const createPlanCheckout = (orgId: string, payload: PlanCheckout) =>
  api<{ url: string }>(`/orgs/${orgId}/billing/plan/checkout`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
