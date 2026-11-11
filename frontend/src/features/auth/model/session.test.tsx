import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "./session";
import type { RegisterPayload, User } from "./types";

// Mock the boundaries the provider reaches across: the auth endpoints, the
// shared API client (tryRefresh), and the org-id storage helper.
vi.mock("../api/endpoints");
vi.mock("../../../shared/api", () => ({
  tryRefresh: vi.fn(),
  getAccessToken: vi.fn(() => null),
  setAccessToken: vi.fn(),
  setImpersonationGuard: vi.fn(),
}));
vi.mock("../../../shared/lib/storage", () => ({
  clearStoredOrgId: vi.fn(),
}));
vi.mock("../../../shared/lib/track", () => ({
  identifyUser: vi.fn(),
  resetAnalytics: vi.fn(),
  setAnalyticsSuspended: vi.fn(),
  track: vi.fn(),
}));

import * as endpoints from "../api/endpoints";
import { tryRefresh } from "../../../shared/api";
import { clearStoredOrgId } from "../../../shared/lib/storage";
import {
  identifyUser,
  resetAnalytics,
  setAnalyticsSuspended,
  track,
} from "../../../shared/lib/track";

afterEach(cleanup);

const fakeUser: User = {
  id: "u1",
  email: "ada@example.com",
  first_name: "Ada",
  last_name: "Lovelace",
  name: "Ada Lovelace",
  is_superuser: false,
  marketing_opt_in: false,
  analytics_opt_out: false,
  email_verified: true,
  created_at: "2024-01-01T00:00:00Z",
};

// Captures the live context value so tests can drive login/register/logout.
let captured: ReturnType<typeof useAuth> | null = null;

function Probe() {
  const auth = useAuth();
  // Capture in an effect (not during render) so the auth API is reachable from
  // tests without a render-phase side effect.
  useEffect(() => {
    captured = auth;
  });
  return (
    <div>
      <span data-testid="loading">{String(auth.loading)}</span>
      <span data-testid="user">{auth.user?.email ?? "none"}</span>
    </div>
  );
}

function renderProvider() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(queryClient, "clear");
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  );
  return { queryClient, ...utils };
}

beforeEach(() => {
  vi.clearAllMocks();
  captured = null;
});

describe("AuthProvider mount", () => {
  it("restores the session when refresh and /me succeed", async () => {
    vi.mocked(tryRefresh).mockResolvedValue(true);
    vi.mocked(endpoints.fetchMe).mockResolvedValue(fakeUser);

    renderProvider();

    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));
    expect(screen.getByTestId("user")).toHaveTextContent("ada@example.com");
    expect(endpoints.fetchMe).toHaveBeenCalledTimes(1);
  });

  it("stays logged out when refresh fails", async () => {
    vi.mocked(tryRefresh).mockResolvedValue(false);

    renderProvider();

    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));
    expect(screen.getByTestId("user")).toHaveTextContent("none");
    expect(endpoints.fetchMe).not.toHaveBeenCalled();
  });

  it("stays logged out when refresh succeeds but /me rejects", async () => {
    vi.mocked(tryRefresh).mockResolvedValue(true);
    vi.mocked(endpoints.fetchMe).mockRejectedValue(new Error("nope"));

    renderProvider();

    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));
    expect(screen.getByTestId("user")).toHaveTextContent("none");
  });
});

describe("AuthProvider actions", () => {
  it("login() sets the user from the endpoint result", async () => {
    vi.mocked(tryRefresh).mockResolvedValue(false);
    vi.mocked(endpoints.login).mockResolvedValue(fakeUser);

    renderProvider();
    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));

    await act(async () => {
      await captured!.login("ada@example.com", "secret123");
    });

    expect(endpoints.login).toHaveBeenCalledWith("ada@example.com", "secret123");
    expect(screen.getByTestId("user")).toHaveTextContent("ada@example.com");
  });

  it("register() registers then logs in to set the user", async () => {
    vi.mocked(tryRefresh).mockResolvedValue(false);
    vi.mocked(endpoints.register).mockResolvedValue(false);
    vi.mocked(endpoints.login).mockResolvedValue(fakeUser);

    renderProvider();
    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));

    const payload: RegisterPayload = {
      first_name: "Ada",
      last_name: "Lovelace",
      email: "ada@example.com",
      password: "secret123",
      password_confirmation: "secret123",
      terms_accepted: true,
      marketing_opt_in: false,
    };
    await act(async () => {
      await captured!.register(payload);
    });

    expect(endpoints.register).toHaveBeenCalledWith(payload);
    expect(endpoints.login).toHaveBeenCalledWith("ada@example.com", "secret123");
    expect(screen.getByTestId("user")).toHaveTextContent("ada@example.com");
  });

  it("register() does not log in when the server requires email verification first", async () => {
    vi.mocked(tryRefresh).mockResolvedValue(false);
    vi.mocked(endpoints.register).mockResolvedValue(true);
    vi.mocked(endpoints.login).mockClear();

    renderProvider();
    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("false"));

    let verificationRequired: boolean | undefined;
    await act(async () => {
      verificationRequired = await captured!.register({
        first_name: "Ada",
        last_name: "Lovelace",
        email: "ada@example.com",
        password: "secret123",
        password_confirmation: "secret123",
        terms_accepted: true,
        marketing_opt_in: false,
      });
    });

    expect(verificationRequired).toBe(true);
    expect(endpoints.login).not.toHaveBeenCalled();
  });

  it("logout() clears the user, the query cache, and the stored org id", async () => {
    vi.mocked(tryRefresh).mockResolvedValue(true);
    vi.mocked(endpoints.fetchMe).mockResolvedValue(fakeUser);
    vi.mocked(endpoints.logout).mockResolvedValue(undefined);

    const { queryClient } = renderProvider();
    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("ada@example.com"));

    await act(async () => {
      await captured!.logout();
    });

    expect(endpoints.logout).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("user")).toHaveTextContent("none");
    expect(queryClient.clear).toHaveBeenCalledTimes(1);
    expect(clearStoredOrgId).toHaveBeenCalledTimes(1);
  });
});

describe("AuthProvider analytics lifecycle", () => {
  async function mounted(restored: boolean) {
    vi.mocked(tryRefresh).mockResolvedValue(restored);
    if (restored) vi.mocked(endpoints.fetchMe).mockResolvedValue(fakeUser);
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
  }

  it("a silently restored session identifies the user but is not a login", async () => {
    await mounted(true);
    expect(identifyUser).toHaveBeenCalledWith(fakeUser);
    expect(track).not.toHaveBeenCalled();
  });

  it("a logged-out visitor is never identified", async () => {
    await mounted(false);
    expect(identifyUser).not.toHaveBeenCalled();
    expect(track).not.toHaveBeenCalled();
  });

  it("login() identifies first, then fires user_logged_in exactly once", async () => {
    await mounted(false);
    vi.mocked(endpoints.login).mockResolvedValue(fakeUser);
    await act(() => captured!.login("ada@example.com", "pw"));
    expect(track).toHaveBeenCalledTimes(1);
    expect(track).toHaveBeenCalledWith("user_logged_in", { method: "email" });
    expect(vi.mocked(identifyUser).mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(track).mock.invocationCallOrder[0],
    );
  });

  it("a failed login fires nothing", async () => {
    await mounted(false);
    vi.mocked(endpoints.login).mockRejectedValue(new Error("bad credentials"));
    await act(async () => {
      await captured!.login("ada@example.com", "nope").catch(() => {});
    });
    expect(identifyUser).not.toHaveBeenCalled();
    expect(track).not.toHaveBeenCalled();
  });

  it("register() fires user_signed_up (not also a login) without the email", async () => {
    await mounted(false);
    vi.mocked(endpoints.register).mockResolvedValue(false);
    vi.mocked(endpoints.login).mockResolvedValue(fakeUser);
    const payload: RegisterPayload = {
      first_name: "Ada",
      last_name: "Lovelace",
      email: "ada@example.com",
      password: "pw",
      password_confirmation: "pw",
      terms_accepted: true,
      marketing_opt_in: true,
    };
    await act(() => captured!.register(payload));
    expect(track).toHaveBeenCalledTimes(1);
    expect(track).toHaveBeenCalledWith("user_signed_up", {
      method: "email",
      marketing_opt_in: true,
    });
  });

  it("logout() fires user_logged_out before the call and resets only on success", async () => {
    await mounted(true);
    vi.mocked(track).mockClear();
    vi.mocked(endpoints.logout).mockRejectedValueOnce(new Error("network"));
    await act(async () => {
      await captured!.logout().catch(() => {});
    });
    expect(resetAnalytics).not.toHaveBeenCalled(); // still signed in

    vi.mocked(endpoints.logout).mockResolvedValue(undefined);
    await act(() => captured!.logout());
    expect(track).toHaveBeenLastCalledWith("user_logged_out");
    expect(resetAnalytics).toHaveBeenCalledTimes(1);
    expect(vi.mocked(track).mock.invocationCallOrder.at(-1)!).toBeLessThan(
      vi.mocked(endpoints.logout).mock.invocationCallOrder.at(-1)!,
    );
  });

  it("refreshUser() re-identifies so a changed opt-out applies immediately", async () => {
    await mounted(true);
    const optedOut = { ...fakeUser, analytics_opt_out: true };
    vi.mocked(endpoints.fetchMe).mockResolvedValue(optedOut);
    await act(() => captured!.refreshUser());
    expect(identifyUser).toHaveBeenLastCalledWith(optedOut);
  });

  it("impersonation suspends analytics and restores the admin identity on exit", async () => {
    await mounted(true);
    const target = { ...fakeUser, id: "customer-1", email: "customer@example.com" };
    vi.mocked(endpoints.fetchMe).mockResolvedValue(target);
    await act(() => captured!.startImpersonation("imp-token"));
    expect(setAnalyticsSuspended).toHaveBeenLastCalledWith(true);
    // The customer is never identified to analytics by the admin's session.
    expect(identifyUser).not.toHaveBeenCalledWith(target);

    act(() => captured!.exitImpersonation());
    expect(setAnalyticsSuspended).toHaveBeenLastCalledWith(false);
    expect(identifyUser).toHaveBeenLastCalledWith(fakeUser);
  });
});

describe("useAuth", () => {
  it("throws when used outside an AuthProvider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    function Orphan() {
      useAuth();
      return null;
    }
    expect(() => render(<Orphan />)).toThrow("useAuth must be used within AuthProvider");
    spy.mockRestore();
  });
});
