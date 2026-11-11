import { type ReactNode } from "react";

import { MK_MONO } from "./styles";

// Mono fact chip: stack names, counts, short identifiers.
export default function Chip({
  children,
  size = "md",
  className = "",
}: {
  children: ReactNode;
  // "sm" sits inline inside an eyebrow label.
  size?: "sm" | "md";
  className?: string;
}) {
  return (
    <span
      className={`${MK_MONO} inline-block whitespace-nowrap rounded bg-[var(--mk-chip)] tabular-nums text-[var(--carbon)] ${
        size === "sm" ? "px-1.5 py-0.5 text-[11px]" : "px-2 py-1 text-xs"
      } ${className}`}
    >
      {children}
    </span>
  );
}
