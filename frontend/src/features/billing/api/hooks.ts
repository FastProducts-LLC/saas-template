// Domain hooks: components talk to these, never to endpoints or queryClient.
// The portal mutation owns the Stripe redirect side effect.

import { useCallback } from "react";
import type { PlanCheckout } from "../model/types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EVENTS } from "../../../shared/lib/events";
import { track } from "../../../shared/lib/track";
import * as endpoints from "./endpoints";
import { billingKeys } from "./keys";

export function useBillingAccount(orgId: string | undefined) {
  return useQuery({
    queryKey: billingKeys.account(orgId ?? ""),
    queryFn: () => endpoints.getBillingAccount(orgId!),
    enabled: !!orgId,
  });
}

/** Admin/owner-gated — pass `enabled` to avoid 403s for members. */
export function useInvoices(orgId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: billingKeys.invoices(orgId ?? ""),
    queryFn: () => endpoints.listInvoices(orgId!),
    enabled: !!orgId && enabled,
  });
}

/** Opens the Stripe billing portal for the org. */
export function useBillingPortal(orgId: string) {
  return useMutation({
    mutationFn: () => endpoints.createPortal(orgId),
    onSuccess: ({ url }) => {
      track(EVENTS.billing_portal_opened, { product: "credits" });
      window.location.href = url;
    },
  });
}

export function usePlans() {
  return useQuery({ queryKey: billingKeys.plans, queryFn: endpoints.listPlans });
}
export function useBillingPlan(orgId: string | undefined) {
  return useQuery({
    queryKey: billingKeys.plan(orgId ?? ""),
    queryFn: () => endpoints.getBillingPlan(orgId!),
    enabled: !!orgId,
  });
}
export function useRefreshBilling(orgId: string) {
  const client = useQueryClient();
  return useCallback(() => {
    void client.invalidateQueries({ queryKey: billingKeys.plan(orgId) });
    void client.invalidateQueries({ queryKey: billingKeys.account(orgId) });
    void client.invalidateQueries({ queryKey: billingKeys.invoices(orgId) });
  }, [client, orgId]);
}
export function usePlanCheckout(orgId: string) {
  const refresh = useRefreshBilling(orgId);
  return useMutation({
    mutationFn: (payload: PlanCheckout) => endpoints.createPlanCheckout(orgId, payload),
    onSuccess: ({ url }, { plan, interval }) => {
      track(EVENTS.plan_checkout_started, { plan, interval });
      refresh();
      window.location.href = url;
    },
  });
}
