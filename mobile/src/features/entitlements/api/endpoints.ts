import { api } from "../../../shared/api";
import type { Entitlements } from "../model/types";

export const getEntitlements = (orgId: string) =>
  api<Entitlements>(`/orgs/${orgId}/entitlements`);
