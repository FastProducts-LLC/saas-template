import { api } from "../../../shared/api";
import type { ActionCost, CreditHistory, Wallet } from "../model/types";

export const listActionCosts = () => api<ActionCost[]>("/credits/actions");

export const getWallet = (orgId: string) => api<Wallet>(`/orgs/${orgId}/credits`);

export const getHistory = (orgId: string, limit = 20, offset = 0) =>
  api<CreditHistory>(`/orgs/${orgId}/credits/history?limit=${limit}&offset=${offset}`);
