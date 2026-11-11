import { type ReactNode } from "react";
import { NavLink } from "react-router-dom";

// Sidebar link. The active item gets a sand fill and the system's lime
// marker; everything else stays quiet until hovered.
export default function NavItem({
  to,
  label,
  icon,
  trailing,
  end = false,
  "data-testid": testId,
  "data-tour": tourId,
}: {
  to: string;
  label: string;
  icon?: ReactNode;
  // Right-aligned extra, e.g. a credit balance stamp.
  trailing?: ReactNode;
  // Match the path exactly (for index routes).
  end?: boolean;
  "data-testid"?: string;
  "data-tour"?: string;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      data-testid={testId}
      data-tour={tourId}
      className={({ isActive }) =>
        `group relative flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors ${
          isActive
            ? "bg-[var(--mist)] font-medium text-[var(--ink)]"
            : "text-[var(--slate)] hover:bg-[var(--mist)]/60 hover:text-[var(--ink)]"
        }`
      }
    >
      {({ isActive }) => (
        <>
          <span
            aria-hidden
            className={`absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-full bg-[var(--lime)] transition-opacity ${
              isActive ? "opacity-100" : "opacity-0"
            }`}
          />
          {icon && (
            <span
              className={`flex h-4 w-4 shrink-0 items-center justify-center ${
                isActive ? "text-[var(--ink)]" : "text-[var(--slate)] group-hover:text-[var(--ink)]"
              }`}
            >
              {icon}
            </span>
          )}
          <span className="min-w-0 flex-1 truncate">{label}</span>
          {trailing}
        </>
      )}
    </NavLink>
  );
}
