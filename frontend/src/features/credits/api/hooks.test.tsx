import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  HISTORY_PAGE_SIZE,
  useActionCosts,
  useBuyCreditPack,
  useCreditHistory,
  useCreditPacks,
  useCreditUsage,
  useSetMemberLimit,
  useWallet,
} from "./hooks";
import type {
  ActionCost,
  CreditHistory,
  CreditPackSpec,
  CreditUsage,
  MemberLimit,
  Wallet,
} from "../model/types";

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

const wallet: Wallet = {
  balance: 100,
  reserved: 0,
  monthly_allowance: 50,
  allowance_period: null,
  pending_holds: [],
};
const history: CreditHistory = { items: [], total: 0 };
const actionCost: ActionCost = { action: "image_gpt", name: "Image (GPT)", cost: 5 };
const packSpec: CreditPackSpec = {
  pack: "starter",
  name: "Starter",
  credits: 100,
  price_cents: 1000,
  unit_price_cents: 10,
  discount_pct: 0,
  purchasable: true,
};

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

describe("useActionCosts", () => {
  it("fetches the action cost table", async () => {
    mocked.listActionCosts.mockResolvedValue([actionCost]);

    const { result } = renderHook(() => useActionCosts(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([actionCost]);
    expect(mocked.listActionCosts).toHaveBeenCalledTimes(1);
  });
});

describe("useWallet", () => {
  it("fetches the wallet for a given org", async () => {
    mocked.getWallet.mockResolvedValue(wallet);

    const { result } = renderHook(() => useWallet("o1"), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(wallet);
    expect(mocked.getWallet).toHaveBeenCalledWith("o1");
  });

  it("is disabled when orgId is missing", () => {
    const { result } = renderHook(() => useWallet(undefined), { wrapper: makeWrapper() });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mocked.getWallet).not.toHaveBeenCalled();
  });

  it("keys the query per org so two orgs trigger two fetches", async () => {
    mocked.getWallet.mockResolvedValue(wallet);
    const wrapper = makeWrapper(); // share one client so caching is exercised

    const a = renderHook(() => useWallet("o1"), { wrapper });
    await waitFor(() => expect(a.result.current.isSuccess).toBe(true));

    const b = renderHook(() => useWallet("o2"), { wrapper });
    await waitFor(() => expect(b.result.current.isSuccess).toBe(true));

    expect(mocked.getWallet).toHaveBeenCalledTimes(2);
    expect(mocked.getWallet).toHaveBeenCalledWith("o1");
    expect(mocked.getWallet).toHaveBeenCalledWith("o2");
  });
});

describe("useCreditHistory", () => {
  it("fetches a page with the right limit/offset", async () => {
    mocked.getHistory.mockResolvedValue(history);

    const { result } = renderHook(() => useCreditHistory("o1", 2), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(history);
    expect(mocked.getHistory).toHaveBeenCalledWith("o1", HISTORY_PAGE_SIZE, 2 * HISTORY_PAGE_SIZE);
  });

  it("is disabled when orgId is missing", () => {
    const { result } = renderHook(() => useCreditHistory(undefined, 0), {
      wrapper: makeWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mocked.getHistory).not.toHaveBeenCalled();
  });

  it("keys the query per org so two orgs trigger two fetches", async () => {
    mocked.getHistory.mockResolvedValue(history);
    const wrapper = makeWrapper();

    const a = renderHook(() => useCreditHistory("o1", 0), { wrapper });
    await waitFor(() => expect(a.result.current.isSuccess).toBe(true));

    const b = renderHook(() => useCreditHistory("o2", 0), { wrapper });
    await waitFor(() => expect(b.result.current.isSuccess).toBe(true));

    expect(mocked.getHistory).toHaveBeenCalledTimes(2);
  });
});

describe("useCreditPacks", () => {
  it("fetches the purchasable credit packs", async () => {
    mocked.listCreditPacks.mockResolvedValue([packSpec]);

    const { result } = renderHook(() => useCreditPacks(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([packSpec]);
    expect(mocked.listCreditPacks).toHaveBeenCalledTimes(1);
  });
});

describe("useBuyCreditPack", () => {
  it("creates a pack checkout session and redirects to the returned url", async () => {
    mocked.createCreditPackCheckout.mockResolvedValue({ url: "https://stripe.test/pack" });

    const { result } = renderHook(() => useBuyCreditPack("o1"), { wrapper: makeWrapper() });
    result.current.mutate("growth");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mocked.createCreditPackCheckout).toHaveBeenCalledWith("o1", "growth");
    expect(window.location.href).toBe("https://stripe.test/pack");
  });
});

const usage: CreditUsage = { period: "2026-07", items: [], total_actors: 0, total_credits: 0 };

describe("useCreditUsage", () => {
  it("fetches usage for the given org and period", async () => {
    mocked.getUsage.mockResolvedValue(usage);

    const { result } = renderHook(() => useCreditUsage("o1", "2026-07"), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(usage);
    expect(mocked.getUsage).toHaveBeenCalledWith("o1", "2026-07");
  });

  it("is disabled when orgId is missing", () => {
    const { result } = renderHook(() => useCreditUsage(undefined, "2026-07"), {
      wrapper: makeWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mocked.getUsage).not.toHaveBeenCalled();
  });

  it("keys the query per period so changing the period refetches", async () => {
    mocked.getUsage.mockResolvedValue(usage);
    const wrapper = makeWrapper();

    const a = renderHook(() => useCreditUsage("o1", "2026-07"), { wrapper });
    await waitFor(() => expect(a.result.current.isSuccess).toBe(true));

    const b = renderHook(() => useCreditUsage("o1", "2026-06"), { wrapper });
    await waitFor(() => expect(b.result.current.isSuccess).toBe(true));

    expect(mocked.getUsage).toHaveBeenCalledTimes(2);
    expect(mocked.getUsage).toHaveBeenCalledWith("o1", "2026-06");
  });
});

describe("useSetMemberLimit", () => {
  it("puts the limit for the member", async () => {
    const limit: MemberLimit = {
      user_id: "u1",
      email: "a@x.com",
      monthly_limit: 20,
      used_this_period: 0,
      updated_at: "2026-07-09T00:00:00Z",
    };
    mocked.setMemberLimit.mockResolvedValue(limit);

    const { result } = renderHook(() => useSetMemberLimit("o1"), { wrapper: makeWrapper() });
    result.current.mutate({ userId: "u1", monthlyLimit: 20 });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mocked.setMemberLimit).toHaveBeenCalledWith("o1", "u1", 20);
  });
});
