// Session lifecycle: bootstraps from the SecureStore refresh token on launch,
// exposes signIn/register/signOut, and reacts to session expiry published by
// the API client (dead refresh token → signed out).

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import { setAccessToken, storeRefreshToken, tryRefresh } from "../../../shared/api";
import { initApi } from "../../../shared/api/setup";
import * as endpoints from "../api/endpoints";
import type { RegisterPayload, User } from "./types";

type SessionStatus = "loading" | "signedOut" | "signedIn";

interface SessionValue {
  status: SessionStatus;
  user: User | null;
  signIn: (email: string, password: string) => Promise<void>;
  /** Resolves true when the account must be confirmed by email before
   * sign-in (verify-first signup) — no session was started. */
  register: (payload: RegisterPayload) => Promise<boolean>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SessionStatus>("loading");
  const [user, setUser] = useState<User | null>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    initApi(() => {
      // Refresh token rejected mid-session — drop straight to signed out.
      setUser(null);
      setStatus("signedOut");
    });
    (async () => {
      try {
        if (await tryRefresh()) {
          setUser(await endpoints.getMe());
          setStatus("signedIn");
        } else {
          setStatus("signedOut");
        }
      } catch {
        setStatus("signedOut");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const session = await endpoints.login(email, password);
    setAccessToken(session.access_token);
    await storeRefreshToken(session.refresh_token);
    setUser(session.user);
    setStatus("signedIn");
  }, []);

  const register = useCallback(
    async (payload: RegisterPayload) => {
      const result = await endpoints.register(payload);
      if (result && "verification_required" in result) return true;
      await signIn(payload.email, payload.password);
      return false;
    },
    [signIn],
  );

  const signOut = useCallback(async () => {
    try {
      await endpoints.logout();
    } catch {
      // Revocation is best-effort — local sign-out always proceeds.
    }
    setAccessToken(null);
    await storeRefreshToken(null);
    queryClient.clear();
    setUser(null);
    setStatus("signedOut");
  }, [queryClient]);

  const refreshUser = useCallback(async () => {
    setUser(await endpoints.getMe());
  }, []);

  const value = useMemo(
    () => ({ status, user, signIn, register, signOut, refreshUser }),
    [status, user, signIn, register, signOut, refreshUser],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}
