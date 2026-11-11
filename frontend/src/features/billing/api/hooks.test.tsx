import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useBillingAccount, useBillingPortal, useInvoices } from "./hooks";
import type { BillingAccount, Invoice } from "../model/types";

vi.mock("./endpoints");

import * as endpoints from "./endpoints";

const mocked = vi.mocked(endpoints);

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return wrapper;
}

const account: BillingAccount = { has_billing_account: true };
const invoice: Invoice = {
  id: "in_1",
  number: "0001",
  status: "paid",
  amount_due: 2000,
  currency: "usd",
  created: "2026-01-01T00:00:00Z",
  hosted_invoice_url: null,
  invoice_pdf: null,
};

// jsdom throws on real navigation, so replace location with a writable stub
// and assert the redirect target the mutation sets.
let location: { href: string };

beforeEach(() => {
  vi.clearAllMocks();
  location = { href: "" };
  Object.defineProperty(window, "location", {
    configurable: true,
    writable: true,
    value: location,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useBillingAccount", () => {
  it("fetches the billing account for a given org", async () => {
    mocked.getBillingAccount.mockResolvedValue(account);

    const { result } = renderHook(() => useBillingAccount("o1"), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(account);
    expect(mocked.getBillingAccount).toHaveBeenCalledWith("o1");
  });

  it("is disabled (no fetch) when orgId is missing", async () => {
    const { result } = renderHook(() => useBillingAccount(undefined), { wrapper: makeWrapper() });

    // Disabled queries never run the queryFn.
    expect(result.current.fetchStatus).toBe("idle");
    expect(mocked.getBillingAccount).not.toHaveBeenCalled();
  });
});

describe("useInvoices", () => {
  it("fetches invoices when org is present and enabled", async () => {
    mocked.listInvoices.mockResolvedValue([invoice]);

    const { result } = renderHook(() => useInvoices("o1", true), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([invoice]);
    expect(mocked.listInvoices).toHaveBeenCalledWith("o1");
  });

  it("does not fetch when not enabled even with an org", () => {
    const { result } = renderHook(() => useInvoices("o1", false), { wrapper: makeWrapper() });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mocked.listInvoices).not.toHaveBeenCalled();
  });

  it("does not fetch when orgId is missing", () => {
    const { result } = renderHook(() => useInvoices(undefined, true), { wrapper: makeWrapper() });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mocked.listInvoices).not.toHaveBeenCalled();
  });
});

describe("useBillingPortal", () => {
  it("opens the billing portal and redirects to the returned url", async () => {
    mocked.createPortal.mockResolvedValue({ url: "https://stripe.test/portal" });

    const { result } = renderHook(() => useBillingPortal("o1"), { wrapper: makeWrapper() });
    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mocked.createPortal).toHaveBeenCalledWith("o1");
    expect(window.location.href).toBe("https://stripe.test/portal");
  });
});
