import { Stamp } from "../../../shared/ui";

/** The "N% off" badge shown next to a credit pack; renders nothing at 0%. */
export function PackDiscountStamp({ pct, className = "" }: { pct: number; className?: string }) {
  if (pct <= 0) return null;
  return (
    <Stamp
      data-testid="credits-pack-discount"
      className={`border-[var(--teal)] text-[var(--teal-deep)] ${className}`.trim()}
    >
      {pct}% off
    </Stamp>
  );
}
