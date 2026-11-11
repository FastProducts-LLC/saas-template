export type EntitlementKey = "seats" | "api_keys";
export interface Entitlement {
  key: EntitlementKey;
  limit: number | null;
  used: number;
  included: boolean;
  source: "plan" | "override";
  expires_at: string | null;
}
export interface Entitlements {
  plan: string;
  entitlements: Entitlement[];
}
