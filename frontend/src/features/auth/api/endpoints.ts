import { api, setAccessToken } from "../../../shared/api";

import type { RegisterPayload, SessionResponse, User } from "../model/types";

export async function login(email: string, password: string): Promise<User> {
  const session = await api<SessionResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setAccessToken(session.access_token);
  return session.user;
}

/** Resolves true when the server runs verify-first signup
 * (SIGNUP_ENUMERATION_PROTECTION): the answer is the same whether or not the
 * email already had an account, and sign-in only works after the emailed
 * link is used — so the caller must not try to log in. */
export async function register(payload: RegisterPayload): Promise<boolean> {
  const body = await api<{ verification_required?: boolean } | undefined>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return body?.verification_required === true;
}

export async function logout(): Promise<void> {
  await api("/auth/logout", { method: "POST" });
  setAccessToken(null);
}

export function fetchMe(): Promise<User> {
  return api<User>("/auth/me");
}

export function updateMarketingOptIn(optIn: boolean): Promise<User> {
  return api<User>("/auth/me", {
    method: "PATCH",
    body: JSON.stringify({ marketing_opt_in: optIn }),
  });
}

export function updateAnalyticsOptOut(optOut: boolean): Promise<User> {
  return api<User>("/auth/me", {
    method: "PATCH",
    body: JSON.stringify({ analytics_opt_out: optOut }),
  });
}

export function updateProfile(firstName: string, lastName: string): Promise<User> {
  return api<User>("/auth/me", {
    method: "PATCH",
    body: JSON.stringify({ first_name: firstName, last_name: lastName }),
  });
}

export async function changePassword(
  currentPassword: string,
  password: string,
  passwordConfirmation: string,
): Promise<void> {
  // Revokes every session; the response carries a fresh access token so the
  // current one survives.
  const session = await api<{ access_token: string }>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({
      current_password: currentPassword,
      password,
      password_confirmation: passwordConfirmation,
    }),
  });
  setAccessToken(session.access_token);
}

export async function forgotPassword(email: string): Promise<void> {
  await api("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(
  token: string,
  password: string,
  passwordConfirmation: string,
): Promise<void> {
  await api("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({
      token,
      password,
      password_confirmation: passwordConfirmation,
    }),
  });
}

export async function verifyEmail(token: string): Promise<void> {
  await api("/auth/verify-email", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export async function resendVerification(): Promise<void> {
  await api("/auth/resend-verification", { method: "POST" });
}
