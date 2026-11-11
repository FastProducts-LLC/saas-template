import type { BillingInterval, Plan, PlanSubscriptionStatus } from "../../../shared/api/enums";

export type CreditPack = "starter" | "growth" | "scale" | "bulk";

export interface CreditPackSpec {
  pack: CreditPack;
  name: string;
  credits: number;
  price_cents: number;
  unit_price_cents: number;
  discount_pct: number;
  purchasable: boolean;
}

export interface BillingAccount {
  has_billing_account: boolean;
}

export interface Invoice {
  id: string;
  number: string | null;
  status: string;
  amount_due: number;
  currency: string;
  created: string;
  hosted_invoice_url: string | null;
  invoice_pdf: string | null;
}

export function formatPrice(cents: number, currency = "usd"): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(cents / 100);
}

export interface BillingPlan {
  plan: Plan;
  subscription: {
    plan: Plan;
    interval: BillingInterval;
    status: PlanSubscriptionStatus;
    current_period_end: string | null;
    cancel_at_period_end: boolean;
  } | null;
}
