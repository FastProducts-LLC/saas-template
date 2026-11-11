// App chrome shared by the workspace and platform-admin layouts: a grouped
// sidebar that stays pinned on desktop and becomes a drawer below `lg`, with
// a slim top bar holding the menu button. DESIGN.md "App navigation".

import { useState, type ReactNode } from "react";

export default function SidebarShell({
  title,
  header,
  nav,
  footer,
  banner,
  children,
}: {
  // Shown in the mobile top bar next to the menu button.
  title: string;
  // Top of the sidebar: wordmark, context switcher.
  header: ReactNode;
  // NavGroup / NavItem elements.
  nav: ReactNode;
  // Bottom of the sidebar: account block, cross-links.
  footer: ReactNode;
  // Full-width strip above everything (e.g. the impersonation warning).
  banner?: ReactNode;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="flex min-h-screen flex-col bg-[var(--paper)]">
      {banner}
      <div className="flex flex-1">
        {open && (
          <button
            type="button"
            aria-label="Close menu"
            data-testid="nav-drawer-backdrop"
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-30 bg-[var(--ink)]/30 lg:hidden"
          />
        )}
        <aside
          data-testid="nav-sidebar"
          // Following any link inside the drawer closes it.
          onClick={(e) => {
            if ((e.target as HTMLElement).closest("a")) setOpen(false);
          }}
          className={`fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col border-r border-[var(--line)] bg-white transition-transform duration-200 lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:translate-x-0 ${
            open ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="px-4 pb-3 pt-5">{header}</div>
          <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-2">{nav}</nav>
          <div className="border-t border-[var(--line)] p-3">{footer}</div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-[var(--line)] bg-white px-4 lg:hidden">
            <button
              type="button"
              aria-label="Open menu"
              aria-expanded={open}
              data-testid="nav-menu-button"
              onClick={() => setOpen(true)}
              className="flex h-9 w-9 items-center justify-center rounded-md text-[var(--ink)] hover:bg-[var(--mist)]"
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path
                  d="M3 6h14M3 10h14M3 14h14"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
            </button>
            <span className="truncate text-sm font-medium text-[var(--ink)]">{title}</span>
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
