import { type MouseEventHandler, type ReactNode } from "react";
import { Link } from "react-router-dom";

// Marketing buttons. Lime is the single primary action per view; soft is the
// secondary; ghost is a quiet nav-level action; outline is for carbon bands.
// Label weight is 400 — emphasis comes from the fill.
const VARIANTS = {
  lime: "bg-[var(--lime)] text-[var(--carbon)] hover:bg-[var(--lime-deep)]",
  soft: "bg-[var(--mk-chip)] text-[var(--carbon)] hover:bg-[var(--mk-hair)]",
  ghost: "text-[var(--carbon)] hover:bg-[var(--mk-chip)]",
  outline: "border border-white/20 text-white hover:bg-white/10",
} as const;

const SIZES = {
  md: "h-10 rounded-md px-4 text-sm",
  lg: "h-12 rounded-lg px-5 text-base",
} as const;

type Props = {
  children: ReactNode;
  variant?: keyof typeof VARIANTS;
  size?: keyof typeof SIZES;
  // Router destination; omit for a plain <button>.
  to?: string;
  onClick?: MouseEventHandler<HTMLElement>;
  className?: string;
  "data-testid"?: string;
};

export default function MkButton({
  children,
  variant = "lime",
  size = "md",
  to,
  onClick,
  className = "",
  "data-testid": testId,
}: Props) {
  const classes = `gd-press inline-flex items-center justify-center gap-2 whitespace-nowrap transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--carbon)] focus-visible:ring-offset-2 ${SIZES[size]} ${VARIANTS[variant]} ${className}`;
  if (to !== undefined) {
    return (
      <Link to={to} onClick={onClick} data-testid={testId} className={classes}>
        {children}
      </Link>
    );
  }
  return (
    <button type="button" onClick={onClick} data-testid={testId} className={classes}>
      {children}
    </button>
  );
}
