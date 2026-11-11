import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useDirectory, useMembershipCheckout, useMyCommunity, useSendMessage } from "./hooks";
import { communityKeys } from "./keys";
import type { DirectoryPage, MyCommunity } from "../model/types";

vi.mock("./endpoints");
vi.mock("../../../shared/lib/track", () => ({
  track: vi.fn(),
}));

import * as endpoints from "./endpoints";

const mocked = vi.mocked(endpoints);

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function makeWrapper(client = makeClient()) {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { wrapper, client };
}

const me: MyCommunity = {
  profile: {
    id: "p1",
    handle: "jane",
    display_name: "Jane",
    bio: null,
    avatar_url: null,
    created_at: "2026-01-01T00:00:00Z",
  },
  membership: {
    tier: "free",
    subscription_status: "none",
    is_premium: false,
    current_period_end: null,
    cancel_at_period_end: false,
    is_banned: false,
  },
};

const directory: DirectoryPage = {
  items: [
    {
      handle: "jane",
      display_name: "Jane",
      bio: null,
      avatar_url: null,
      tier: "premium",
      joined_at: "2026-01-01T00:00:00Z",
    },
  ],
  total: 1,
  page: 1,
  page_size: 24,
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

describe("useMyCommunity", () => {
  it("fetches profile + membership state", async () => {
    mocked.getMyCommunity.mockResolvedValue(me);

    const { result } = renderHook(() => useMyCommunity(), {
      wrapper: makeWrapper().wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.profile?.handle).toBe("jane");
  });
});

describe("useDirectory", () => {
  it("fetches a page keyed by search + page", async () => {
    mocked.listMembers.mockResolvedValue(directory);

    const { result } = renderHook(() => useDirectory("ja", 1), {
      wrapper: makeWrapper().wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mocked.listMembers).toHaveBeenCalledWith("ja", 1);
    expect(result.current.data?.total).toBe(1);
  });
});

describe("useMembershipCheckout", () => {
  it("redirects to the Stripe checkout URL", async () => {
    mocked.createMembershipCheckout.mockResolvedValue({
      url: "https://stripe.test/checkout",
    });

    const { result } = renderHook(() => useMembershipCheckout(), {
      wrapper: makeWrapper().wrapper,
    });
    result.current.mutate("monthly");

    await waitFor(() => expect(location.href).toBe("https://stripe.test/checkout"));
  });
});

describe("useSendMessage", () => {
  it("invalidates the thread and conversation list on success", async () => {
    mocked.sendMessage.mockResolvedValue({
      id: "m1",
      body: "hi",
      mine: true,
      deleted: false,
      created_at: "2026-01-01T00:00:00Z",
    });

    const { wrapper, client } = makeWrapper();
    const invalidate = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useSendMessage("c1"), { wrapper });
    result.current.mutate("hi");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mocked.sendMessage).toHaveBeenCalledWith("c1", "hi");
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: communityKeys.messages("c1"),
    });
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: communityKeys.conversations,
    });
  });
});
