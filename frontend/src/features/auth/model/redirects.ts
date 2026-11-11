import { ROUTES } from "../../../shared/lib/routes";

const DEFAULT_AUTH_REDIRECT = ROUTES.dashboard;

const DESTINATION_LABELS: Record<string, string> = {
  [ROUTES.admin.overview]: "Admin",
  [ROUTES.apiKeys]: "API keys",
  [ROUTES.billing]: "Billing",
  [ROUTES.dashboard]: "Dashboard",
  [ROUTES.members]: "Members",
  [ROUTES.organizations.create]: "New workspace",
  [ROUTES.profile]: "Profile",
  [ROUTES.settings]: "Settings",
};

export function getSafeAuthRedirect(next: string | null) {
  if (!next) return DEFAULT_AUTH_REDIRECT;
  if (!next.startsWith("/") || next.startsWith("//")) return DEFAULT_AUTH_REDIRECT;

  try {
    const url = new URL(next, "https://app.local");
    if (url.origin !== "https://app.local") return DEFAULT_AUTH_REDIRECT;
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return DEFAULT_AUTH_REDIRECT;
  }
}

export function getDestinationLabel(next: string | null) {
  const path = getSafeAuthRedirect(next).split(/[?#]/)[0];
  return DESTINATION_LABELS[path] ?? "your workspace";
}

export function buildAuthPath(path: string, next: string | null) {
  const safeNext = getSafeAuthRedirect(next);
  if (safeNext === DEFAULT_AUTH_REDIRECT) return path;
  return `${path}?next=${encodeURIComponent(safeNext)}`;
}
