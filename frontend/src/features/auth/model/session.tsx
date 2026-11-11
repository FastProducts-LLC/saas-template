// Auth session: restores the session on load (via the refresh cookie) and
// exposes login/register/logout to the app.
//
// Impersonation (platform admins only): the admin's access token + user are
// stashed in refs, the short-lived impersonation token is swapped in, and a
// guard in shared/api/client.ts prevents the 401→refresh path from silently
// minting the ADMIN's token mid-impersonation (the refresh cookie is still
// the admin's). When the impersonation token expires, we exit cleanly back
// to the admin identity instead.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  getAccessToken,
  setAccessToken,
  setImpersonationGuard,
  tryRefresh,
} from "../../../shared/api";
import { EVENTS } from "../../../shared/lib/events";
import { clearStoredOrgId } from "../../../shared/lib/storage";
import {
  identifyUser,
  resetAnalytics,
  setAnalyticsSuspended,
  track,
} from "../../../shared/lib/track";
import * as endpoints from "../api/endpoints";
import type { RegisterPayload, User } from "./types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  /** Resolves true when the account must be confirmed by email before
   * sign-in (verify-first signup) — no session was started. */
  register: (payload: RegisterPayload) => Promise<boolean>;
  logout: () => Promise<void>;
  /** Re-fetch /me after a profile mutation so the UI reflects it everywhere. */
  refreshUser: () => Promise<void>;
  /** Non-null while a platform admin is browsing as another user. */
  impersonating: { name: string; email: string } | null;
  startImpersonation: (token: string) => Promise<void>;
  exitImpersonation: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [impersonating, setImpersonating] = useState<{ name: string; email: string } | null>(null);
  const adminToken = useRef<string | null>(null);
  const adminUser = useRef<User | null>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    (async () => {
      if (await tryRefresh()) {
        const me = await endpoints.fetchMe().catch(() => null);
        setUser(me);
        // Silent restore: identify only — a restored session is not a login.
        if (me) identifyUser(me);
      }
      setLoading(false);
    })();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const u = await endpoints.login(email, password);
    setUser(u);
    identifyUser(u);
    track(EVENTS.user_logged_in, { method: "email" });
  }, []);

  const register = useCallback(async (payload: RegisterPayload) => {
    const verificationRequired = await endpoints.register(payload);
    // Verify-first signup: no session yet, and the server won't say whether
    // an account was created — nothing to identify or count here.
    if (verificationRequired) return true;
    const u = await endpoints.login(payload.email, payload.password);
    setUser(u);
    identifyUser(u);
    // Counted as a signup, not also as a login.
    track(EVENTS.user_signed_up, { method: "email", marketing_opt_in: payload.marketing_opt_in });
    return false;
  }, []);

  const logout = useCallback(async () => {
    // Before the call: afterwards the access token is gone and the event
    // could no longer be attributed to the session.
    track(EVENTS.user_logged_out);
    await endpoints.logout();
    setUser(null);
    resetAnalytics(); // only reached when the logout actually succeeded
    queryClient.clear();
    clearStoredOrgId();
  }, [queryClient]);

  const refreshUser = useCallback(async () => {
    const me = await endpoints.fetchMe();
    setUser(me);
    identifyUser(me); // picks up a changed analytics opt-out immediately
  }, []);

  const exitImpersonation = useCallback(() => {
    setImpersonationGuard(false);
    setAccessToken(adminToken.current);
    setUser(adminUser.current);
    setAnalyticsSuspended(false);
    if (adminUser.current) identifyUser(adminUser.current);
    adminToken.current = null;
    adminUser.current = null;
    setImpersonating(null);
    queryClient.clear();
    clearStoredOrgId();
  }, [queryClient]);

  const startImpersonation = useCallback(
    async (token: string) => {
      adminToken.current = getAccessToken();
      adminUser.current = user;
      setAccessToken(token);
      try {
        const target = await endpoints.fetchMe();
        setImpersonationGuard(true, () => exitImpersonation());
        // The admin's clicks must never be recorded as the customer's
        // activity — every sink stays paused until impersonation ends.
        setAnalyticsSuspended(true);
        setUser(target);
        setImpersonating({ name: target.name, email: target.email });
        queryClient.clear();
        clearStoredOrgId();
      } catch (err) {
        // Roll back to the admin identity if the target lookup fails.
        setAccessToken(adminToken.current);
        adminToken.current = null;
        adminUser.current = null;
        throw err;
      }
    },
    [user, queryClient, exitImpersonation],
  );

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        refreshUser,
        impersonating,
        startImpersonation,
        exitImpersonation,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
