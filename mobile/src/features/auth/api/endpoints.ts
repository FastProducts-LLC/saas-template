import {
  api,
  getStoredRefreshToken,
  setAccessToken,
  storeRefreshToken,
} from "../../../shared/api";
import type { RegisterPayload, SessionResponse, User } from "../model/types";

export const login = (email: string, password: string) =>
  api<SessionResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

/** `verification_required` is set when the server runs verify-first signup:
 * same answer whether or not the email had an account, and sign-in only
 * works after the emailed link is used — so don't try to sign in. */
export const register = (payload: RegisterPayload) =>
  api<User | { verification_required: true }>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const getMe = () => api<User>("/auth/me");

export const updateMe = (payload: Partial<Pick<User, "first_name" | "last_name" | "marketing_opt_in">>) =>
  api<User>("/auth/me", { method: "PATCH", body: JSON.stringify(payload) });

export const forgotPassword = (email: string) =>
  api<void>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) });

export const resendVerification = () =>
  api<void>("/auth/resend-verification", { method: "POST" });

/** Change password. The backend revokes EVERY session and issues a fresh
 * pair (mobile flow: in the body) — persist it or this device is signed out
 * along with the stolen ones. */
export async function changePassword(payload: {
  current_password: string;
  password: string;
  password_confirmation: string;
}): Promise<void> {
  const tokens = await api<{ access_token: string; refresh_token: string | null }>(
    "/auth/change-password",
    { method: "POST", body: JSON.stringify(payload) },
  );
  setAccessToken(tokens.access_token);
  await storeRefreshToken(tokens.refresh_token);
}

/** Best-effort server-side revocation of the stored refresh token. */
export async function logout(): Promise<void> {
  const refresh = await getStoredRefreshToken();
  if (!refresh) return;
  await api<void>("/auth/logout", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refresh }),
  });
}
