import { api } from "../../../shared/api";
import type { ApiKey, ApiKeyCreated } from "../model/types";

export const listApiKeys = (orgId: string) => api<ApiKey[]>(`/orgs/${orgId}/api-keys`);

export const createApiKey = (orgId: string, name: string) =>
  api<ApiKeyCreated>(`/orgs/${orgId}/api-keys`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });

export const deleteApiKey = (orgId: string, keyId: string) =>
  api<void>(`/orgs/${orgId}/api-keys/${keyId}`, { method: "DELETE" });
