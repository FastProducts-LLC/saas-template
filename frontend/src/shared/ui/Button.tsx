import { type ButtonHTMLAttributes } from "react";

import Spinner from "./Spinner";

// "danger" is text-first for destructive triggers that open a confirmation
// step. "danger-confirm" is filled — reserved for the final confirmation
// action itself (DESIGN.md: "filled red only for final confirmation
// actions").
type Variant = "primary" | "secondary" | "danger" | "danger-confirm";

const VARIANT_STYLES: Record<Variant, string> = {
  primary:
    "rounded bg-[var(--ink)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--ink-soft)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--teal)]/30 disabled:opacity-50",
  secondary:
    "rounded border border-[var(--line)] bg-transparent px-4 py-2 text-sm font-semibold text-[var(--ink)] transition-colors hover:bg-[var(--mist)]/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--teal)]/30 disabled:opacity-50",
  danger:
    "rounded bg-transparent px-4 py-2 text-sm font-semibold text-[var(--danger)] transition-colors hover:bg-[var(--mist)]/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--teal)]/30 disabled:opacity-50",
  "danger-confirm":
    "rounded bg-[var(--danger)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:brightness-110 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--teal)]/30 disabled:opacity-50",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
}

// Shared button matching the primary/secondary/danger styles used across the
// auth, billing, and settings pages. `loading` disables the button and shows
// an inline spinner before the label.
export default function Button({
  variant = "primary",
  loading = false,
  disabled,
  className = "",
  type = "button",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={`${VARIANT_STYLES[variant]} ${loading ? "inline-flex items-center justify-center gap-2" : ""} ${className}`}
      {...props}
    >
      {loading && <Spinner className="h-4 w-4" />}
      {children}
    </button>
  );
}
