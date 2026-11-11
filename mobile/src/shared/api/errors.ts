// Errors a screen is presenting inline. The global toast host waits a beat
// and skips anything claimed here, so a form showing <ErrorNote> never ALSO
// gets a duplicate toast. Rendering <ErrorNote> claims automatically.
const claimed = new WeakSet<object>();

export const INLINE_CLAIM_GRACE_MS = 150;

/** Mark an error as shown inline (suppresses its global toast). */
export function claimError(err: unknown): void {
  if (typeof err === "object" && err !== null) claimed.add(err);
}

export function isErrorClaimed(err: unknown): boolean {
  return typeof err === "object" && err !== null && claimed.has(err);
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
