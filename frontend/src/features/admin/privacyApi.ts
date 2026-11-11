import { api } from "../../shared/api";
// PrivacyRequestStatus is generated from the backend domain enum (scripts/gen_enums.py).
import type { PrivacyRequestStatus } from "../../shared/api/enums";
import type { Page } from "./api";

export type PrivacyRequestType = "access" | "delete" | "suppress";
export type { PrivacyRequestStatus };

export interface PrivacyRequest {
  id: string;
  request_type: PrivacyRequestType;
  status: PrivacyRequestStatus;
  requester_email: string | null;
  requester_name: string | null;
  subject_email: string | null;
  subject_phone: string | null;
  subject_consumer_key: string | null;
  subject_first_name: string | null;
  subject_last_name: string | null;
  request_payload: Record<string, unknown> | null;
  subject_email_hash: string | null;
  subject_phone_hash: string | null;
  subject_consumer_key_hash: string | null;
  admin_notes: string | null;
  provider_reference: string | null;
  provider_forwarded_at: string | null;
  fulfilled_at: string | null;
  rejection_reason: string | null;
  payload_purged_at: string | null;
  deadline_at: string | null;
  created_at: string;
  updated_at: string;
}

const qs = (params: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
};

export const listPrivacyRequests = (status: string, page: number) =>
  api<Page<PrivacyRequest>>(`/admin/privacy-requests${qs({ status, page })}`);

export const getPrivacyRequest = (id: string) =>
  api<PrivacyRequest>(`/admin/privacy-requests/${id}`);

export const verifyPrivacyRequest = (id: string) =>
  api<PrivacyRequest>(`/admin/privacy-requests/${id}/verify`, { method: "POST" });

export const forwardPrivacyRequest = (id: string, provider_reference: string, notes?: string) =>
  api<PrivacyRequest>(`/admin/privacy-requests/${id}/forward`, {
    method: "POST",
    body: JSON.stringify({ provider_reference, notes }),
  });

export const fulfillPrivacyRequest = (
  id: string,
  body: { provider_reference?: string; notes?: string; also_forward?: boolean },
) =>
  api<PrivacyRequest>(`/admin/privacy-requests/${id}/fulfill`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const closePrivacyRequest = (id: string, notes?: string) =>
  api<PrivacyRequest>(`/admin/privacy-requests/${id}/close`, {
    method: "POST",
    body: JSON.stringify({ notes }),
  });

export const rejectPrivacyRequest = (id: string, reason: string) =>
  api<PrivacyRequest>(`/admin/privacy-requests/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });

export const submitPrivacyRequest = (body: {
  request_type: PrivacyRequestType;
  requester_email: string;
  requester_name?: string;
  subject_email?: string;
  subject_phone?: string;
  subject_consumer_key?: string;
  subject_first_name?: string;
  subject_last_name?: string;
  notes?: string;
}) =>
  api<{
    id: string;
    request_type: PrivacyRequestType;
    status: PrivacyRequestStatus;
    message: string;
  }>("/privacy/requests", { method: "POST", body: JSON.stringify(body) });
