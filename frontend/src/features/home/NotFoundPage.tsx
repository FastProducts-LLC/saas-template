// 404 page. Auth-aware: signed-in users get a link back to the dashboard,
// anonymous visitors get links home and to sign in. Styled like the public
// pages with the shared AuthCard shell.

import { Link } from "react-router-dom";

import { ROUTES } from "../../shared/lib/routes";
import { AuthCard, Button } from "../../shared/ui";
import { useAuth } from "../auth";

export default function NotFoundPage() {
  const { user, loading } = useAuth();

  return (
    <AuthCard>
      <p
        data-testid="not-found-page"
        className="text-sm font-medium uppercase tracking-wide text-[var(--teal-deep)]"
      >
        404
      </p>
      <h1 className="mt-2 font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight text-[var(--ink)]">
        Page not found
      </h1>
      <p className="mt-2 text-sm text-[var(--slate)]/75">
        The page you’re looking for doesn’t exist or may have moved.
      </p>

      <div className="mt-6">
        {!loading && user ? (
          <Link to={ROUTES.dashboard} data-testid="not-found-dashboard-link" className="block">
            <Button className="w-full">Back to dashboard</Button>
          </Link>
        ) : (
          <div className="flex flex-col gap-3">
            <Link to={ROUTES.home} data-testid="not-found-home-link" className="block">
              <Button className="w-full">Go home</Button>
            </Link>
            <Link to={ROUTES.auth.login} data-testid="not-found-login-link" className="block">
              <Button variant="secondary" className="w-full">
                Sign in
              </Button>
            </Link>
          </div>
        )}
      </div>
    </AuthCard>
  );
}
