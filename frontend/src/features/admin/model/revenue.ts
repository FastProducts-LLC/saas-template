export interface Revenue {
  currency: string;
  mrr_cents: number;
  arr_cents: number;
  active: number;
  trialing: number;
  past_due: number;
  canceling: number;
  new_last_30d: number;
  canceled_last_30d: number;
  computed_at: string;
  by_plan: { plan: string; interval: string; count: number; mrr_cents: number }[];
}
