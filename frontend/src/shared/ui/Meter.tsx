export interface MeterSegment {
  value: number;
  /** Fill class, e.g. "bg-[var(--ink)]". */
  className: string;
}

interface MeterProps {
  segments: MeterSegment[];
  /** Full scale; defaults to the sum of the segments. */
  max?: number;
  /** Accessible summary of what the bar shows. */
  label: string;
  size?: "sm" | "md";
  className?: string;
}

// Flat horizontal bar for proportions (credit balance vs holds, seats used).
// Segments stack left to right on a sand track. No gradients, no rounding
// beyond the 2px app radius.
export default function Meter({ segments, max, label, size = "md", className = "" }: MeterProps) {
  const total = max ?? segments.reduce((sum, s) => sum + s.value, 0);
  return (
    <div
      role="img"
      aria-label={label}
      className={`flex w-full overflow-hidden rounded-[2px] bg-[var(--mist)] ${
        size === "sm" ? "h-1.5" : "h-2.5"
      } ${className}`}
    >
      {total > 0 &&
        segments.map((s, i) =>
          s.value > 0 ? (
            <span
              key={i}
              className={`h-full transition-[width] duration-500 ease-[var(--ease-out-soft)] ${s.className}`}
              style={{ width: `${Math.min(100, (s.value / total) * 100)}%` }}
            />
          ) : null,
        )}
    </div>
  );
}
