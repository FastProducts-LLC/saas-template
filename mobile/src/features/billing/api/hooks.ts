// Checkout/portal happen in the system browser (Stripe pages can't be
// embedded). useRefetchOnForeground refreshes wallet + invoices when the app
// comes back, so a completed purchase shows up without manual pull-to-refresh.

import { useEffect } from "react";
import { AppState } from "react-native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as WebBrowser from "expo-web-browser";

import { entitlementKeys } from "../../entitlements";
import { creditKeys } from "../../credits";
import type { CreditPack } from "../model/types";
import * as endpoints from "./endpoints";
import { billingKeys } from "./keys";

export function usePacks() {
  return useQuery({
    queryKey: billingKeys.packs,
    queryFn: endpoints.listPacks,
    staleTime: 60 * 60 * 1000,
  });
}

export function useBillingAccount(orgId: string | undefined) {
  return useQuery({
    queryKey: billingKeys.account(orgId ?? ""),
    queryFn: () => endpoints.getBillingAccount(orgId!),
    enabled: !!orgId,
  });
}

export function useInvoices(orgId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: billingKeys.invoices(orgId ?? ""),
    queryFn: () => endpoints.listInvoices(orgId!),
    enabled: !!orgId && enabled,
  });
}

/** Invalidate money-related caches whenever the app returns to foreground. */
export function useRefetchOnForeground(orgId: string | undefined) {
  const queryClient = useQueryClient();
  useEffect(() => {
    const sub = AppState.addEventListener("change", (state) => {
      if (state !== "active" || !orgId) return;
      queryClient.invalidateQueries({ queryKey: billingKeys.plan(orgId) });
      queryClient.invalidateQueries({ queryKey: entitlementKeys.snapshot(orgId) });
      queryClient.invalidateQueries({ queryKey: creditKeys.wallet(orgId) });
      queryClient.invalidateQueries({ queryKey: creditKeys.history(orgId) });
      queryClient.invalidateQueries({ queryKey: billingKeys.invoices(orgId) });
      queryClient.invalidateQueries({ queryKey: billingKeys.account(orgId) });
    });
    return () => sub.remove();
  }, [orgId, queryClient]);
}

export function useCheckout(orgId: string | undefined) {
  return useMutation({
    mutationFn: async (pack: CreditPack) => {
      const { url } = await endpoints.checkoutPack(orgId!, pack);
      await WebBrowser.openBrowserAsync(url);
    },
  });
}

export function useBillingPortal(orgId: string | undefined) {
  return useMutation({
    mutationFn: async () => {
      const { url } = await endpoints.openPortal(orgId!);
      await WebBrowser.openBrowserAsync(url);
    },
  });
}

export function useBillingPlan(orgId: string | undefined) {
  return useQuery({
    queryKey: billingKeys.plan(orgId ?? ""),
    queryFn: () => endpoints.getBillingPlan(orgId!),
    enabled: !!orgId,
  });
}
