import { type ReactNode } from "react";

import Chip from "./Chip";
import { MK_EYEBROW_BASE } from "./styles";

const TONES = {
  light: "text-[var(--mk-muted)]",
  strong: "text-[var(--carbon)]",
  dark: "text-white/60",
} as const;

// Uppercase micro-label above a heading. `chip` appends a mono fact
// ("LABEL: [06]"). Tones: "light" (muted), "strong" (full carbon), "dark"
// (for carbon bands).
export default function Eyebrow({
  children,
  chip,
  tone = "light",
  className = "",
}: {
  children: ReactNode;
  chip?: ReactNode;
  tone?: keyof typeof TONES;
  className?: string;
}) {
  return (
    <p className={`flex items-center gap-2 ${MK_EYEBROW_BASE} ${TONES[tone]} ${className}`}>
      {children}
      {chip !== undefined && ":"}
      {chip !== undefined && <Chip size="sm">{chip}</Chip>}
    </p>
  );
}
