// Domain hooks: components talk to these, never to endpoints or queryClient.

import { useCallback } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EVENTS } from "../../../shared/lib/events";
import { CREDIT_HISTORY_PAGE_SIZE } from "../../../shared/lib/policy";
import { track } from "../../../shared/lib/track";
import * as endpoints from "./endpoints";
import { creditsKeys } from "./keys";
import type { CreditPack } from "../model/types";

export const HISTORY_PAGE_SIZE = CREDIT_HISTORY_PAGE_SIZE;

export function useActionCosts() {
  return useQuery({
    queryKey: creditsKeys.actionCosts,
    queryFn: endpoints.listActionCosts,
  });
}

export function useWallet(orgId: string | undefined) {
  return useQuery({
    queryKey: creditsKeys.wallet(orgId ?? ""),
    queryFn: () => endpoints.getWallet(orgId!),
    enabled: !!orgId,
  });
}

export function useCreditHistory(orgId: string | undefined, page: number) {
  return useQuery({
    queryKey: creditsKeys.history(orgId ?? "", page),
    queryFn: () => endpoints.getHistory(orgId!, HISTORY_PAGE_SIZE, page * HISTORY_PAGE_SIZE),
    enabled: !!orgId,
  });
}

export function useCreditPacks() {
  return useQuery({
    queryKey: creditsKeys.packs,
    queryFn: endpoints.listCreditPacks,
  });
}

/**
 * Refreshes every credits cache (wallet + history) for an org. The status
 * banner uses this after a successful Stripe redirect, since the balance only
 * changes once the webhook lands.
 */
export function useRefreshCredits(orgId: string | undefined) {
  const queryClient = useQueryClient();
  return useCallback(() => {
    if (!orgId) return;
    queryClient.invalidateQueries({ queryKey: creditsKeys.all(orgId) });
  }, [queryClient, orgId]);
}

/** Starts a Stripe Checkout session for a credit pack and redirects to it. */
export function useBuyCreditPack(orgId: string) {
  return useMutation({
    mutationFn: (pack: CreditPack) => endpoints.createCreditPackCheckout(orgId, pack),
    onSuccess: ({ url }, pack) => {
      // Intent only — the purchase itself is the server-truth
      // `credit_pack_purchased` event written from the Stripe webhook.
      track(EVENTS.checkout_started, { product: "credit_pack", plan: pack });
      window.location.href = url;
    },
  });
}

/** Credits spent in a period, grouped by member / API key. */
export function useCreditUsage(orgId: string | undefined, period: string) {
  return useQuery({
    queryKey: creditsKeys.usage(orgId ?? "", period),
    queryFn: () => endpoints.getUsage(orgId!, period),
    enabled: !!orgId,
  });
}

/** Admin: set a member's monthly credit cap. Refreshes all credits caches. */
export function useSetMemberLimit(orgId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, monthlyLimit }: { userId: string; monthlyLimit: number }) =>
      endpoints.setMemberLimit(orgId, userId, monthlyLimit),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: creditsKeys.all(orgId) });
    },
  });
}

/** Admin: remove a member's monthly credit cap. */
export function useClearMemberLimit(orgId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => endpoints.clearMemberLimit(orgId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: creditsKeys.all(orgId) });
    },
  });
}
