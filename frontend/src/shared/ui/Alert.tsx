import { type ReactNode } from "react";

type Tone = "error" | "success" | "warning" | "info";

const TONE_STYLES: Record<Tone, string> = {
  error: "border-[var(--danger)] text-[var(--danger)]",
  success: "border-[var(--success)] text-[var(--success)]",
  warning: "border-[var(--danger)] text-[var(--danger)]",
  info: "border-[var(--line)] text-[var(--slate)]",
};

interface AlertProps {
  tone: Tone;
  children: ReactNode;
  className?: string;
  "data-testid"?: string;
}

// Inline status banner: bordered, tone-colored text on white — no fill.
export default function Alert({
  tone,
  children,
  className = "",
  "data-testid": testId,
}: AlertProps) {
  return (
    <div
      className={`rounded border bg-white px-4 py-2 text-sm ${TONE_STYLES[tone]} ${className}`}
      role="alert"
      data-testid={testId}
      data-tone={tone}
    >
      {children}
    </div>
  );
}
