import { api } from "../../shared/api";
import type { CreditAction, GenerationStatus } from "../../shared/api/enums";
import type { Role } from "../organizations";

// Generated from the backend domain enums (scripts/gen_enums.py); generation
// kinds are the credit-action values.
export type { GenerationStatus };
export type GenerationKind = CreditAction;

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminStats {
  total_users: number;
  active_users: number;
  total_organizations: number;
}

export interface TimeseriesPoint {
  date: string;
  count: number;
}

export interface CategoryCount {
  label: string;
  count: number;
}

export interface TopCustomer {
  name: string;
  value: number;
}

export interface CreditSummary {
  total_balance: number;
  total_pending_holds: number;
  total_credits_captured: number;
}

export interface CommercialSummary {
  organizations_with_billing_account: number;
  organizations_with_wallet: number;
  negative_wallets: number;
  zero_balance_wallets: number;
  low_balance_wallets: number;
  low_balance_threshold: number;
}

export interface OperationsSummary {
  pending_invitations: number;
  expired_invitations: number;
  open_privacy_requests: number;
  overdue_privacy_requests: number;
  privacy_requests_due_soon: number;
  stale_pending_generations: number;
  expired_credit_holds: number;
}

export interface SecuritySummary {
  superusers: number;
  email_verified_users: number;
  unverified_users: number;
  email_suppressed_users: number;
  active_api_keys: number;
  api_keys_used_30d: number;
  stale_api_keys: number;
  unused_api_keys: number;
}

export interface AdminAnalytics {
  user_signups: TimeseriesPoint[];
  org_signups: TimeseriesPoint[];
  credits_spent_daily: TimeseriesPoint[];
  generations_by_status: CategoryCount[];
  generations_by_kind: CategoryCount[];
  top_customers_by_credits: TopCustomer[];
  credit_summary: CreditSummary;
  commercial_summary: CommercialSummary;
  operations_summary: OperationsSummary;
  security_summary: SecuritySummary;
  recent_admin_actions: CategoryCount[];
}

export interface AdminOrg {
  id: string;
  name: string;
  slug: string;
  created_at: string;
  suspended_at: string | null;
  member_count: number;
  owner_email: string | null;
  owner_name: string | null;
}

export interface AdminOrgMember {
  user_id: string;
  email: string;
  name: string;
  role: Role;
  is_active: boolean;
  joined_at: string;
}

export interface AdminUser {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  organization_count: number;
}

export interface ImpersonationGrant {
  access_token: string;
  user_id: string;
  email: string;
  name: string;
}

export interface AdminWallet {
  organization_id: string;
  organization_name: string;
  balance: number;
  allowance_period: string | null;
  pending_holds: number;
  updated_at: string;
}

export interface AdminCustomerUsage {
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  created_at: string;
  suspended_at: string | null;
  member_count: number;
  owner_email: string | null;
  owner_name: string | null;
  credits_spent: number;
  credit_balance: number | null;
  dollars_spent_cents: number;
  dollar_balance_cents: number | null;
}

export interface AdminGeneration {
  id: string;
  organization_id: string;
  organization_name: string;
  user_id: string | null;
  kind: GenerationKind;
  model: string;
  status: GenerationStatus;
  prompt: string;
  error: string | null;
  credits_cost: number;
  created_at: string;
  completed_at: string | null;
}

export interface AdminInvitation {
  id: string;
  organization_id: string;
  organization_name: string;
  email: string;
  role: Role;
  invited_by_email: string | null;
  expires_at: string;
  created_at: string;
}

export interface AdminAuditEntry {
  id: string;
  actor_email: string | null;
  actor_name: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface ErrorRecord {
  event: string;
  code: string;
  error_id: string;
  method: string;
  path: string;
  status: number;
  ts: string;
  detail?: string;
  query?: string;
  client?: string;
  user_agent?: string;
  traceback?: string;
}

const qs = (params: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
};

export const fetchStats = () => api<AdminStats>("/admin/stats");

export const fetchAnalytics = () => api<AdminAnalytics>("/admin/analytics");

export const listOrgs = (search: string, page: number) =>
  api<Page<AdminOrg>>(`/admin/organizations${qs({ search, page })}`);

export const listOrgMembers = (orgId: string) =>
  api<AdminOrgMember[]>(`/admin/organizations/${orgId}/members`);

export const suspendOrg = (orgId: string) =>
  api<{ id: string; suspended_at: string | null }>(`/admin/organizations/${orgId}/suspend`, {
    method: "POST",
  });

export const unsuspendOrg = (orgId: string) =>
  api<{ id: string; suspended_at: string | null }>(`/admin/organizations/${orgId}/unsuspend`, {
    method: "POST",
  });

export const listUsers = (search: string, page: number) =>
  api<Page<AdminUser>>(`/admin/users${qs({ search, page })}`);

export const deactivateUser = (userId: string) =>
  api<AdminUser>(`/admin/users/${userId}/deactivate`, { method: "POST" });

export const reactivateUser = (userId: string) =>
  api<AdminUser>(`/admin/users/${userId}/reactivate`, { method: "POST" });

export const signOutUserEverywhere = (userId: string) =>
  api<AdminUser>(`/admin/users/${userId}/signout-everywhere`, { method: "POST" });

export const impersonateUser = (userId: string) =>
  api<ImpersonationGrant>(`/admin/users/${userId}/impersonate`, { method: "POST" });

export const listWallets = (search: string, page: number) =>
  api<Page<AdminWallet>>(`/admin/credits${qs({ search, page })}`);

export const listCustomers = (search: string, page: number, sort: string = "joined") =>
  api<Page<AdminCustomerUsage>>(`/admin/customers${qs({ search, page, sort })}`);

export const adjustCredits = (orgId: string, amount: number, description: string) =>
  api<AdminWallet>(`/admin/organizations/${orgId}/credits/adjust`, {
    method: "POST",
    body: JSON.stringify({ amount, description }),
  });

export const listGenerations = (
  status: GenerationStatus | "",
  kind: GenerationKind | "",
  page: number,
) => api<Page<AdminGeneration>>(`/admin/generations${qs({ status, kind, page })}`);

export const listInvitations = (page: number) =>
  api<Page<AdminInvitation>>(`/admin/invitations${qs({ page })}`);

export const revokeInvitation = (invitationId: string) =>
  api<void>(`/admin/invitations/${invitationId}`, { method: "DELETE" });

export const listAuditLog = (page: number) =>
  api<Page<AdminAuditEntry>>(`/admin/audit-log${qs({ page })}`);

export const lookupError = (ref: string) =>
  api<ErrorRecord>(`/admin/errors/${encodeURIComponent(ref)}`);

export const mergeOrgs = (targetId: string, sourceIds: string[]) =>
  api<{ target_id: string; merged_count: number; members_moved: number }>(
    "/admin/organizations/merge",
    {
      method: "POST",
      body: JSON.stringify({ target_id: targetId, source_ids: sourceIds }),
    },
  );

export interface AdminFeatureFlag {
  key: string;
  enabled: boolean;
  updated_by: string | null;
  updated_at: string | null;
}

export const listFeatureFlags = () => api<{ items: AdminFeatureFlag[] }>("/admin/flags");

export const setFeatureFlag = (key: string, enabled: boolean) =>
  api<AdminFeatureFlag>(`/admin/flags/${key}`, {
    method: "PUT",
    body: JSON.stringify({ enabled }),
  });

export interface AdminCommunityMember {
  user_id: string;
  handle: string;
  display_name: string;
  email: string;
  tier: string;
  subscription_status: string;
  is_hidden: boolean;
  is_banned: boolean;
  banned_at: string | null;
  joined_at: string;
}

export const listCommunityMembers = (search: string, page: number) =>
  api<Page<AdminCommunityMember>>(`/admin/community/members${qs({ search, page })}`);

export const setCommunityBan = (userId: string, banned: boolean) =>
  api<void>(`/admin/community/members/${userId}/${banned ? "ban" : "unban"}`, {
    method: "POST",
  });

export const setCommunityHidden = (userId: string, hidden: boolean) =>
  api<void>(`/admin/community/members/${userId}/${hidden ? "hide-profile" : "unhide-profile"}`, {
    method: "POST",
  });
