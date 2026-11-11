import { type ReactNode } from "react";

const STAMP_BASE =
  "inline-flex rounded-[2px] border bg-transparent px-1.5 py-0.5 font-[family-name:var(--font-mono)] text-[11px] font-medium leading-none tracking-normal";

interface StampProps {
  children: ReactNode;
  /** Border/text color tone, e.g. "border-[var(--success)] text-[var(--success)]". */
  className?: string;
  uppercase?: boolean;
  tabularNums?: boolean;
  "data-testid"?: string;
}

// Small bordered mono-font marker — record statuses, transaction types, plan
// badges, credit counts. Never filled: DESIGN.md bans bright badge pills.
export default function Stamp({
  children,
  className = "",
  uppercase = true,
  tabularNums = false,
  "data-testid": testId,
}: StampProps) {
  return (
    <span
      data-testid={testId}
      className={`${STAMP_BASE} ${uppercase ? "uppercase" : ""} ${tabularNums ? "tabular-nums" : ""} ${className}`}
    >
      {children}
    </span>
  );
}
