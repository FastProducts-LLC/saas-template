import { type ReactNode } from "react";

interface PageHeaderProps {
  title: ReactNode;
  /** One sentence on what the page is for. Sans, slate. */
  description?: ReactNode;
  /** Mono fact line under the description, e.g. "Dev Org · Owner". */
  meta?: ReactNode;
  /** Right-aligned actions; the page's single primary action goes last. */
  actions?: ReactNode;
  titleTestId?: string;
  className?: string;
}

// The one page header every app screen uses, so titles, descriptions, and the
// primary action sit in the same place on every page (DESIGN.md "App surface").
export default function PageHeader({
  title,
  description,
  meta,
  actions,
  titleTestId,
  className = "",
}: PageHeaderProps) {
  return (
    <header
      className={`flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between ${className}`}
    >
      <div className="min-w-0">
        <h1
          data-testid={titleTestId}
          className="font-[family-name:var(--font-display)] text-[28px] leading-[1.15] text-[var(--ink)]"
        >
          {title}
        </h1>
        {description && (
          <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-[var(--slate)]">
            {description}
          </p>
        )}
        {meta && (
          <p className="mt-1.5 font-[family-name:var(--font-mono)] text-xs tabular-nums text-[var(--slate)]">
            {meta}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
