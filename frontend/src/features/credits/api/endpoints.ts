import { api } from "../../../shared/api";

import type {
  ActionCost,
  CreditHistory,
  CreditPack,
  CreditPackSpec,
  CreditUsage,
  MemberLimit,
  Wallet,
} from "../model/types";

export const listActionCosts = () => api<ActionCost[]>("/credits/actions");

export const getWallet = (orgId: string) => api<Wallet>(`/orgs/${orgId}/credits`);

export const getHistory = (orgId: string, limit: number, offset: number) =>
  api<CreditHistory>(`/orgs/${orgId}/credits/history?limit=${limit}&offset=${offset}`);

export const listCreditPacks = () => api<CreditPackSpec[]>("/billing/credits/packs");

export const createCreditPackCheckout = (orgId: string, pack: CreditPack) =>
  api<{ url: string }>(`/orgs/${orgId}/billing/credits/checkout`, {
    method: "POST",
    body: JSON.stringify({ pack }),
  });

export const getUsage = (orgId: string, period: string) =>
  api<CreditUsage>(`/orgs/${orgId}/credits/usage?period=${period}`);

export const setMemberLimit = (orgId: string, userId: string, monthlyLimit: number) =>
  api<MemberLimit>(`/orgs/${orgId}/credits/member-limits/${userId}`, {
    method: "PUT",
    body: JSON.stringify({ monthly_limit: monthlyLimit }),
  });

export const clearMemberLimit = (orgId: string, userId: string) =>
  api<void>(`/orgs/${orgId}/credits/member-limits/${userId}`, { method: "DELETE" });
