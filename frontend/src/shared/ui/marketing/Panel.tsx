import { type ReactNode } from "react";

const TONES = {
  sand: "border-[var(--sand-line)] bg-[var(--sand)]",
  canvas: "border-[var(--sand-line)] bg-[var(--canvas)]",
  carbon: "border-white/10 bg-[var(--carbon-soft)] text-white",
} as const;

// Bento surface: 12px radius, 1px border, no shadow. Sand is the default
// container; canvas sits on sand; carbon sits on carbon bands.
export default function Panel({
  children,
  tone = "sand",
  radius = "xl",
  className = "",
  "data-testid": testId,
}: {
  children: ReactNode;
  tone?: keyof typeof TONES;
  // "2xl" is for page-level showcase panels (hero); cards use "xl".
  radius?: "xl" | "2xl";
  className?: string;
  "data-testid"?: string;
}) {
  return (
    <div
      data-testid={testId}
      className={`${radius === "2xl" ? "rounded-2xl" : "rounded-xl"} border ${TONES[tone]} ${className}`}
    >
      {children}
    </div>
  );
}
