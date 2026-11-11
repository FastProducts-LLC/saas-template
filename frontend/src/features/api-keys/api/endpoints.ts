import { api } from "../../../shared/api";
import type { ApiKey, ApiKeyCreatePayload, ApiKeyCreated } from "../model/types";

export const listApiKeys = (orgId: string) => api<ApiKey[]>(`/orgs/${orgId}/api-keys`);

export const createApiKey = (orgId: string, payload: ApiKeyCreatePayload) =>
  api<ApiKeyCreated>(`/orgs/${orgId}/api-keys`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const revokeApiKey = (orgId: string, keyId: string) =>
  api<void>(`/orgs/${orgId}/api-keys/${keyId}`, { method: "DELETE" });
