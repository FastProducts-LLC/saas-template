import { type ReactNode } from "react";

// Labelled cluster of NavItems. Omit `label` for a lead group that needs no
// heading (e.g. a single "Overview" entry).
export default function NavGroup({ label, children }: { label?: string; children: ReactNode }) {
  return (
    <div>
      {label && (
        <p className="px-2.5 pb-1.5 font-[family-name:var(--font-mono)] text-[10px] uppercase tracking-[0.08em] text-[var(--slate)]/80">
          {label}
        </p>
      )}
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}
