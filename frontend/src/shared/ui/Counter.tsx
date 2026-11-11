import { type HTMLAttributes, type ReactNode } from "react";
import { Link } from "react-router-dom";

// Counter blocks (DESIGN.md "Component Language"): one shared rule across the
// top of the group, large tabular numerals, sentence-case labels, vertical
// hairlines between counters. No boxes, no icons.
export function CounterStrip({
  className = "",
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`grid grid-cols-1 divide-y divide-[var(--line)] border-y border-[var(--line)] sm:auto-cols-fr sm:grid-flow-col sm:divide-x sm:divide-y-0 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

interface CounterProps {
  value: ReactNode;
  label: ReactNode;
  /** Mono fact under the label, e.g. "2 actions in progress". */
  detail?: ReactNode;
  /** Optional extra line (e.g. a low-balance hint). */
  hint?: ReactNode;
  /** Makes the whole counter a link. */
  to?: string;
  testId?: string;
  linkTestId?: string;
}

export function Counter({ value, label, detail, hint, to, testId, linkTestId }: CounterProps) {
  const body = (
    <>
      <p
        data-testid={testId}
        className="font-[family-name:var(--font-display)] text-[40px] leading-none text-[var(--ink)] tabular-nums"
      >
        {value}
      </p>
      <p className="mt-2.5 text-[13px] text-[var(--slate)]">{label}</p>
      {detail && (
        <p className="mt-1 font-[family-name:var(--font-mono)] text-xs tabular-nums text-[var(--slate)]/75">
          {detail}
        </p>
      )}
      {hint}
    </>
  );
  const pad = "block py-5 sm:px-6 sm:first:pl-0";
  if (to) {
    return (
      <Link
        to={to}
        data-testid={linkTestId}
        className={`${pad} group transition-colors hover:bg-[var(--paper)]`}
      >
        {body}
      </Link>
    );
  }
  return <div className={pad}>{body}</div>;
}
