export interface BillingAccount {
  has_billing_account: boolean;
}

export interface Invoice {
  id: string;
  number: string | null;
  status: string;
  amount_due: number; // cents
  currency: string;
  created: string; // ISO datetime
  hosted_invoice_url: string | null;
  invoice_pdf: string | null;
}

export type { Plan, BillingInterval, PlanSubscriptionStatus } from "../../../shared/api/enums";
import type { Plan, BillingInterval, PlanSubscriptionStatus } from "../../../shared/api/enums";

export interface PlanSpec {
  plan: Plan;
  name: string;
  monthly_price_cents: number;
  annual_price_cents: number;
  monthly_credits: number;
  purchasable: Record<BillingInterval, boolean>;
}
export interface PlanSubscription {
  plan: Plan;
  interval: BillingInterval;
  status: PlanSubscriptionStatus;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
}
export interface BillingPlan {
  plan: Plan;
  subscription: PlanSubscription | null;
}
export interface PlanCheckout {
  plan: Plan;
  interval: BillingInterval;
}
