import type { CSSProperties, ReactNode } from "react";

/** Grid for credit-pack cells: one column on mobile, one column per pack on
 * sm+ — the count comes from the API response, never a hardcoded class. */
export function PackGrid({
  count,
  className = "",
  children,
}: {
  count: number;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      data-testid="credits-pack-grid"
      className={`grid grid-cols-1 sm:grid-cols-[repeat(var(--pack-cols),minmax(0,1fr))] ${className}`.trim()}
      style={{ "--pack-cols": count } as CSSProperties}
    >
      {children}
    </div>
  );
}
