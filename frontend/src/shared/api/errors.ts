import { ApiError } from "./client";

// Errors a component is presenting inline. The global error UI waits a beat
// before toasting and skips anything claimed here, so a form that shows its
// own error never ALSO gets a duplicate toast. Claims are automatic: calling
// getErrorMessage() or rendering <ErrorAlert> claims the error.
const claimed = new WeakSet<object>();

/** Mark an error as shown inline (suppresses its global toast). */
export function claimError(err: unknown): void {
  if (typeof err === "object" && err !== null) claimed.add(err);
}

export function isErrorClaimed(err: unknown): boolean {
  return typeof err === "object" && err !== null && claimed.has(err);
}

/** Maps any thrown value to a user-presentable message (catalog copy first).
 * Claims the error: whoever asks for the message is displaying it. */
export function getErrorMessage(err: unknown): string {
  claimError(err);
  return err instanceof ApiError ? err.userMessage : "Something went wrong.";
}

/** True when `err` is the given catalog code. A match claims the error:
 * callers branch on a code precisely to present it their own way (upgrade
 * prompt, redirect, inline field message) instead of the generic toast. */
export function isApiErrorWithCode(err: unknown, code: string): err is ApiError {
  const match = err instanceof ApiError && err.code === code;
  if (match) claimError(err);
  return match;
}

/** "members.0.email" -> "Email"; "__root__" -> null (form-level message). */
export function fieldLabel(key: string): string | null {
  if (key === "__root__") return null;
  const last =
    key
      .split(".")
      .filter((part) => !/^\d+$/.test(part))
      .pop() ?? key;
  const words = last.replace(/_/g, " ").trim();
  return words ? words[0].toUpperCase() + words.slice(1) : null;
}
