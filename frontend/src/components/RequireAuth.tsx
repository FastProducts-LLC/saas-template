import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../features/auth";
import { OrgProvider } from "../features/organizations";
import { ROUTES } from "../shared/lib/routes";
import { FullScreenSpinner } from "../shared/ui";

export default function RequireAuth() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <FullScreenSpinner />;
  }
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`${ROUTES.auth.login}?next=${next}`} replace />;
  }
  return (
    <OrgProvider>
      <Outlet />
    </OrgProvider>
  );
}
