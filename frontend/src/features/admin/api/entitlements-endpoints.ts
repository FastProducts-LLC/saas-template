import { api } from "../../../shared/api";
import type { EntitlementKey } from "../../entitlements";
import type { AdminEntitlements, Override, OverridePayload } from "../model/entitlements";
import type { Revenue } from "../model/revenue";
export const getRevenue = () => api<Revenue>("/admin/revenue");
export const getOrgEntitlements = (orgId: string) =>
  api<AdminEntitlements>(`/admin/organizations/${orgId}/entitlements`);
export const setOverride = (orgId: string, key: EntitlementKey, payload: OverridePayload) =>
  api<Override>(`/admin/organizations/${orgId}/entitlements/${key}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
export const removeOverride = (orgId: string, key: EntitlementKey) =>
  api<void>(`/admin/organizations/${orgId}/entitlements/${key}`, { method: "DELETE" });
