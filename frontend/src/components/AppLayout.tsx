import { useEffect, type SVGProps } from "react";
import { Link, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../features/auth";
import { useFeature } from "../features/config";
import { CreditBalanceBadge, useWallet } from "../features/credits";
import { ROUTES } from "../shared/lib/routes";
import { BRAND } from "../shared/lib/brand";
import { useOrg } from "../features/organizations";
import { setUserProperties } from "../shared/lib/analytics";
import { Avatar, FullScreenSpinner } from "../shared/ui";
import { NavGroup, NavItem, SidebarShell } from "../shared/ui/shell";

function iconProps(props: SVGProps<SVGSVGElement>): SVGProps<SVGSVGElement> {
  return {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
    ...props,
  };
}

const NAV_ICONS = {
  dashboard: (props: SVGProps<SVGSVGElement>) => (
    <svg {...iconProps(props)}>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </svg>
  ),
  credits: (props: SVGProps<SVGSVGElement>) => (
    <svg {...iconProps(props)}>
      <circle cx="12" cy="12" r="9" />
      <path d="M14.5 9.5a3 3 0 1 0 0 5" />
    </svg>
  ),
  members: (props: SVGProps<SVGSVGElement>) => (
    <svg {...iconProps(props)}>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
      <path d="M16 5a3.5 3.5 0 0 1 0 7" />
      <path d="M17.5 14.5a6.5 6.5 0 0 1 4 5.5" />
    </svg>
  ),
  billing: (props: SVGProps<SVGSVGElement>) => (
    <svg {...iconProps(props)}>
      <rect x="2.5" y="5" width="19" height="14" rx="2" />
      <line x1="2.5" y1="10" x2="21.5" y2="10" />
    </svg>
  ),
  apiKeys: (props: SVGProps<SVGSVGElement>) => (
    <svg {...iconProps(props)}>
      <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.78 7.78 5.5 5.5 0 0 1 7.78-7.78zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
    </svg>
  ),
  features: (props: SVGProps<SVGSVGElement>) => (
    <svg {...iconProps(props)}>
      <rect x="3" y="4" width="7" height="7" rx="1.5" />
      <rect x="14" y="4" width="7" height="7" rx="1.5" />
      <rect x="3" y="15" width="7" height="5" rx="1.5" />
      <path d="M14 17.5h7" />
      <path d="M17.5 14v7" />
    </svg>
  ),
  community: (props: SVGProps<SVGSVGElement>) => (
    <svg {...iconProps(props)}>
      <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
    </svg>
  ),
  docs: (props: SVGProps<SVGSVGElement>) => (
    <svg {...iconProps(props)}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6M9 17h4" />
    </svg>
  ),
  admin: (props: SVGProps<SVGSVGElement>) => (
    <svg {...iconProps(props)}>
      <path d="M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  ),
  signOut: (props: SVGProps<SVGSVGElement>) => (
    <svg {...iconProps(props)}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="M16 17l5-5-5-5" />
      <path d="M21 12H9" />
    </svg>
  ),
  settings: (props: SVGProps<SVGSVGElement>) => (
    <svg {...iconProps(props)}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.03 1.56V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1.11-1.56 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.56-1.03H3a2 2 0 1 1 0-4h.09a1.7 1.7 0 0 0 1.56-1.11 1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34h.08A1.7 1.7 0 0 0 10.1 3.6V3.5a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1.03 1.56h.08a1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87v.08a1.7 1.7 0 0 0 1.56 1.03H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.56 1.03z" />
    </svg>
  ),
} as const;

type NavEntry = { to: string; label: string; icon: keyof typeof NAV_ICONS; tourId?: string };

// Sidebar information architecture: who and what the workspace is, then what
// it consumes, then reference material. Community only exists while its
// feature flag is on.
function navGroups(communityEnabled: boolean): { label: string; items: NavEntry[] }[] {
  return [
    {
      label: "Workspace",
      items: [
        { to: ROUTES.dashboard, label: "Dashboard", icon: "dashboard" },
        { to: ROUTES.members, label: "Members", icon: "members" },
        ...(communityEnabled
          ? [{ to: ROUTES.community.list, label: "Community", icon: "community" as const }]
          : []),
        { to: ROUTES.settings, label: "Settings", icon: "settings" },
      ],
    },
    {
      label: "Billing & usage",
      items: [
        { to: ROUTES.billing, label: "Billing", icon: "billing", tourId: "nav-billing" },
        { to: ROUTES.apiKeys, label: "API keys", icon: "apiKeys", tourId: "nav-api-keys" },
      ],
    },
    {
      label: "Resources",
      items: [
        { to: ROUTES.saasFeatures, label: "SaaS features", icon: "features" },
        { to: ROUTES.docs, label: "API docs", icon: "docs" },
      ],
    },
  ];
}

export default function AppLayout() {
  const { user, logout, impersonating, exitImpersonation } = useAuth();
  const { orgs, loading, currentOrg, setCurrentOrgId } = useOrg();
  const navigate = useNavigate();
  const location = useLocation();
  // The Community module is admin-toggleable — its nav entry only exists
  // while the flag is on (routes are additionally gated by RequireFeature).
  const communityEnabled = useFeature("community");

  const orgId = currentOrg?.id;
  const orgRole = currentOrg?.role;
  const { data: wallet } = useWallet(orgId || undefined);

  useEffect(() => {
    if (!orgRole) return;
    setUserProperties({
      org_role: orgRole,
      account_type: wallet != null ? (wallet.balance > 0 ? "paid" : "free") : undefined,
    });
  }, [orgRole, wallet]);

  if (loading) {
    return <FullScreenSpinner />;
  }
  if (!currentOrg) {
    return <Navigate to={ROUTES.organizations.create} replace />;
  }

  const AdminIcon = NAV_ICONS.admin;
  const SignOutIcon = NAV_ICONS.signOut;

  return (
    <SidebarShell
      title={currentOrg.name}
      banner={
        impersonating && (
          // Deliberate exception to the "no filled badges" rule: this is a
          // security-relevant admin state, not a status pill, and it
          // must stay loud enough that an admin can't miss it before taking a
          // consequential action (billing, revocation, data access).
          <div
            data-testid="nav-impersonation-banner"
            className="flex items-center justify-center gap-3 bg-[var(--danger)] px-4 py-2 text-sm font-semibold text-white"
          >
            <span className="font-[family-name:var(--font-mono)] tabular-nums">
              Impersonating {impersonating.name} ({impersonating.email})
            </span>
            <button
              data-testid="nav-exit-impersonation-button"
              onClick={() => {
                exitImpersonation();
                navigate(ROUTES.admin.users);
              }}
              className="rounded border border-white/60 px-3 py-1 font-semibold hover:bg-white/15"
            >
              Exit
            </button>
          </div>
        )
      }
      header={
        <>
          <Link
            to={ROUTES.dashboard}
            data-testid="nav-logo-link"
            className="font-[family-name:var(--font-display)] text-[19px] tracking-tight text-[var(--ink)]"
          >
            {BRAND}
          </Link>
          <label className="mt-4 block">
            <span className="mb-1 block font-[family-name:var(--font-mono)] text-[10px] uppercase tracking-[0.08em] text-[var(--slate)]/80">
              Organization
            </span>
            <select
              data-tour="org-switcher"
              data-testid="nav-org-switcher"
              className="w-full rounded-md border border-[var(--line)] bg-white px-2.5 py-2 text-sm text-[var(--ink)] focus:border-[var(--teal)] focus:outline-none focus:ring-2 focus:ring-[var(--teal)]/15"
              value={currentOrg.id}
              onChange={(e) => {
                if (e.target.value === "__new__") navigate(ROUTES.organizations.create);
                else setCurrentOrgId(e.target.value);
              }}
            >
              {orgs.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
              <option value="__new__">+ New organization</option>
            </select>
          </label>
        </>
      }
      nav={navGroups(Boolean(communityEnabled)).map((group) => (
        <NavGroup key={group.label} label={group.label}>
          {group.items.map((item) => {
            const Icon = NAV_ICONS[item.icon];
            return (
              <NavItem
                key={item.to}
                to={item.to}
                label={item.label}
                end={item.to === ROUTES.dashboard}
                icon={<Icon className="h-4 w-4" />}
                data-tour={item.tourId}
                data-testid={`nav-${item.to.slice(1)}-link`}
                trailing={
                  item.to === ROUTES.billing ? <CreditBalanceBadge orgId={currentOrg.id} /> : null
                }
              />
            );
          })}
        </NavGroup>
      ))}
      footer={
        <>
          {user?.is_superuser && (
            <NavItem
              to={ROUTES.admin.overview}
              label="Platform admin"
              icon={<AdminIcon className="h-4 w-4" />}
              data-testid="nav-admin-link"
            />
          )}
          <Link
            to={ROUTES.profile}
            data-testid="nav-profile-link"
            className="group mt-1 flex items-center gap-2.5 rounded-md px-2.5 py-2 hover:bg-[var(--mist)]/60"
          >
            <Avatar name={user?.name ?? ""} size="sm" />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium text-[var(--ink)]">
                {user?.name}
              </span>
              <span className="block truncate font-[family-name:var(--font-mono)] text-[11px] text-[var(--slate)]">
                {user?.email}
              </span>
            </span>
          </Link>
          <button
            data-testid="nav-logout-button"
            onClick={() => logout().then(() => navigate(ROUTES.auth.login))}
            className="group flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-[var(--slate)] hover:bg-[var(--mist)]/60 hover:text-[var(--ink)]"
          >
            <SignOutIcon className="h-4 w-4" />
            Sign out
          </button>
        </>
      }
    >
      <main className="flex-1 p-5 sm:p-6 lg:p-8">
        {/* Keyed on pathname so every route change replays the entrance animation. */}
        <div key={location.pathname} className="gd-page-in">
          <Outlet />
        </div>
      </main>
    </SidebarShell>
  );
}
