import type { Entitlements, EntitlementKey } from "../../entitlements";
export interface OverridePayload {
  limit_value: number | null;
  expires_at: string | null;
  note: string | null;
}
export interface Override extends OverridePayload {
  key: EntitlementKey;
  created_by_id: string | null;
  updated_at: string;
}
export interface AdminEntitlements extends Entitlements {
  overrides: Override[];
}
export function validateOverride(limit: string, unlimited: boolean, expiry: string, note: string) {
  const fields: Record<string, string> = {};
  if (!unlimited && (!limit.trim() || !Number.isSafeInteger(Number(limit)) || Number(limit) < 0))
    fields.limit_value = "Enter a non-negative integer.";
  if (expiry && (!Number.isFinite(Date.parse(expiry)) || Date.parse(expiry) <= Date.now()))
    fields.expires_at = "Expiry must be in the future.";
  if (note.length > 500) fields.note = "Note must be 500 characters or fewer.";
  return fields;
}

export function localExpiry(value: string | null | undefined) {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}
