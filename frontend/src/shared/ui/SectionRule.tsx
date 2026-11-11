import { type ReactNode } from "react";

interface SectionRuleProps {
  index: string;
  title: string;
  /** Optional right-aligned control (link, toggle) after the hairline. */
  action?: ReactNode;
  id?: string;
  className?: string;
}

// Numbered section heading + hairline rule — the records-instrument pattern
// used to divide a page or panel into zones (DESIGN.md: "structure comes
// from rules and type, never boxes, shadows, or colored chips").
export default function SectionRule({
  index,
  title,
  action,
  id,
  className = "",
}: SectionRuleProps) {
  return (
    <div id={id} className={`flex scroll-mt-6 items-center gap-3 ${className}`}>
      <span className="font-[family-name:var(--font-mono)] text-xs text-[var(--slate)] tabular-nums">
        {index}
      </span>
      <h2 className="shrink-0 text-[15px] font-semibold text-[var(--ink)]">{title}</h2>
      <div className="h-px flex-1 bg-[var(--line)]" />
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
