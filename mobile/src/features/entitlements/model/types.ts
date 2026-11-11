import type { EntitlementKey, Plan } from "../../../shared/api/enums";

export interface Entitlement {
  key: EntitlementKey;
  limit: number | null;
  used: number;
  included: boolean;
  source: "plan" | "override";
  expires_at: string | null;
}

export interface Entitlements {
  plan: Plan;
  entitlements: Entitlement[];
}
