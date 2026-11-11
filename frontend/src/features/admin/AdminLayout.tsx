// Platform-admin shell: superuser-only, sits outside the org-scoped AppLayout.
// The guard here is cosmetic — the backend rejects non-superusers with a 403.
// Nav mirrors AppLayout's left sidebar so admin feels like the rest of the product.

import { Link, Navigate, Outlet } from "react-router-dom";

import { ROUTES } from "../../shared/lib/routes";
import { NavGroup, NavItem, SidebarShell } from "../../shared/ui/shell";
import { useAuth } from "../auth";

// Grouped by the question an operator is asking: how is the business doing,
// who is on the platform, what do we publish, how is the platform configured,
// and can we prove we are compliant.
const navGroups: { label?: string; tabs: { to: string; label: string; section: string }[] }[] = [
  {
    tabs: [{ to: ROUTES.admin.overview, label: "Overview", section: "overview" }],
  },
  {
    label: "Revenue & usage",
    tabs: [
      { to: ROUTES.admin.revenue, label: "Revenue", section: "revenue" },
      { to: ROUTES.admin.customers, label: "Customers", section: "customers" },
      { to: ROUTES.admin.credits, label: "Credits", section: "credits" },
      { to: ROUTES.admin.generations, label: "Generations", section: "generations" },
    ],
  },
  {
    label: "Tenants",
    tabs: [
      { to: ROUTES.admin.orgs, label: "Organizations", section: "orgs" },
      { to: ROUTES.admin.users, label: "Users", section: "users" },
      { to: ROUTES.admin.invitations, label: "Invitations", section: "invitations" },
    ],
  },
  {
    label: "Content & community",
    tabs: [
      { to: ROUTES.admin.blog, label: "Blog", section: "blog" },
      { to: ROUTES.admin.community, label: "Community", section: "community" },
    ],
  },
  {
    label: "Platform",
    tabs: [
      { to: ROUTES.admin.flags, label: "Feature flags", section: "flags" },
      { to: ROUTES.admin.errors, label: "Error lookup", section: "errors" },
    ],
  },
  {
    label: "Compliance",
    tabs: [
      { to: ROUTES.admin.audit, label: "Audit log", section: "audit" },
      { to: ROUTES.admin.privacyRequests, label: "Privacy requests", section: "privacy" },
      { to: ROUTES.admin.compliance, label: "Compliance", section: "compliance" },
    ],
  },
];

export default function AdminLayout() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-[var(--slate)]/55">
        Loading…
      </div>
    );
  }
  if (!user?.is_superuser) {
    return <Navigate to={ROUTES.dashboard} replace />;
  }

  return (
    <SidebarShell
      title="Platform admin"
      header={
        <>
          <div className="flex items-center gap-2">
            <h1 className="font-[family-name:var(--font-display)] text-[19px] tracking-tight text-[var(--ink)]">
              Platform admin
            </h1>
            <span className="rounded-[2px] border border-[var(--danger)] px-1.5 py-0.5 font-[family-name:var(--font-mono)] text-[10px] uppercase leading-none text-[var(--danger)]">
              superuser
            </span>
          </div>
          <p className="mt-1 truncate font-[family-name:var(--font-mono)] text-[11px] text-[var(--slate)]">
            {user.email}
          </p>
        </>
      }
      nav={navGroups.map((group) => (
        <NavGroup key={group.label ?? "lead"} label={group.label}>
          {group.tabs.map((tab) => (
            <NavItem
              key={tab.to}
              to={tab.to}
              label={tab.label}
              end={tab.to === ROUTES.admin.overview}
              data-testid={`admin-nav-${tab.section}-link`}
            />
          ))}
        </NavGroup>
      ))}
      footer={
        <Link
          to={ROUTES.dashboard}
          data-testid="admin-nav-back-to-app-link"
          className="flex items-center gap-2 rounded-md px-2.5 py-2 text-sm text-[var(--slate)] hover:bg-[var(--mist)]/60 hover:text-[var(--ink)]"
        >
          <span aria-hidden>←</span> Back to app
        </Link>
      }
    >
      <main className="min-w-0 flex-1 px-5 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="mx-auto max-w-6xl">
          <Outlet />
        </div>
      </main>
    </SidebarShell>
  );
}
