import { type CSSProperties } from "react";

import { MK_MONO } from "./styles";

export type LedgerFact = { readonly label: string; readonly value: string };

// Mini ledger: the system's signature data texture — a white card of
// label/value rows with every value in mono. `live` adds a pulsing lime dot
// to the header; `tone="dark"` is for carbon bands.
export default function Ledger({
  label,
  facts,
  live = false,
  tone = "light",
  className = "",
  style,
}: {
  label: string;
  facts: readonly LedgerFact[];
  live?: boolean;
  tone?: "light" | "dark";
  className?: string;
  style?: CSSProperties;
}) {
  const dark = tone === "dark";
  return (
    <div
      style={style}
      className={`rounded-lg border p-4 ${
        dark
          ? "border-white/10 bg-white/[0.04]"
          : "border-[var(--sand-line)] bg-[var(--canvas)] shadow-sm"
      } ${className}`}
    >
      <p
        className={`${MK_MONO} flex items-center justify-between gap-3 text-[10px] uppercase tracking-[0.08em] ${
          dark ? "text-white/60" : "text-[var(--mk-muted)]"
        }`}
      >
        {label}
        {live && (
          <span aria-hidden className="mk-pulse h-1.5 w-1.5 rounded-full bg-[var(--lime)]" />
        )}
      </p>
      <dl className="mt-3">
        {facts.map((f) => (
          <div
            key={f.label}
            className={`flex items-baseline justify-between gap-4 border-t py-2 text-[13px] last:pb-0 ${
              dark ? "border-white/10" : "border-[var(--mk-hair)]"
            }`}
          >
            <dt className={dark ? "text-white/60" : "text-[var(--mk-muted)]"}>{f.label}</dt>
            <dd
              className={`${MK_MONO} text-xs tabular-nums ${dark ? "text-white" : "text-[var(--carbon)]"}`}
            >
              {f.value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
