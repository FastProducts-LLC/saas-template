// Presentation vocabulary for the credit ledger — the single copy shared by
// every page that renders transactions or metered actions (dashboard,
// billing, credits). Add new TransactionType / CreditAction entries here.

import type { CreditAction, ReservationStatus, TransactionType } from "./types";

export const TYPE_LABELS: Record<TransactionType, string> = {
  grant: "Credits added",
  hold: "Credits held",
  release: "Refunded",
  expire: "Hold expired",
  adjustment: "Adjustment",
};

export const TYPE_STYLES: Record<TransactionType, string> = {
  grant: "border-[var(--success)] text-[var(--success)]",
  hold: "border-[var(--info)] text-[var(--info)]",
  release: "border-[var(--info)] text-[var(--info)]",
  expire: "border-[var(--danger)] text-[var(--danger)]",
  adjustment: "border-[var(--ink)] text-[var(--ink)]",
};

// A "hold" row's real outcome lives on its reservation: still running,
// finally charged, or refunded.
export const HOLD_OUTCOME: Record<ReservationStatus, { label: string; className: string }> = {
  pending: { label: "In progress", className: "border-[var(--info)] text-[var(--info)]" },
  captured: { label: "Charged", className: "border-[var(--teal)] text-[var(--teal-deep)]" },
  released: { label: "Refunded", className: "border-[var(--info)] text-[var(--info)]" },
  expired: { label: "Expired", className: "border-[var(--danger)] text-[var(--danger)]" },
};

export const ACTION_LABELS: Record<CreditAction, string> = {
  llm_call: "LLM call",
  image_nano_banana: "Image",
  image_gpt: "Image",
  video_veo: "Video",
};

export function actionLabel(action: CreditAction | string | null): string {
  if (!action) return "";
  return ACTION_LABELS[action as CreditAction] ?? action;
}

/** Current usage period as YYYY-MM in UTC — the backend windows periods in
 *  UTC, so local-time month math shows the wrong month near boundaries. */
export function currentPeriodUTC(): string {
  const now = new Date();
  return `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}`;
}
