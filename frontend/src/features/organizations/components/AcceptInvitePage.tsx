import { ErrorAlert } from "../../../shared/ui";
import { useEffect, useRef } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { useAcceptInvitation } from "../api/hooks";
import { useOrg } from "../model/current-org";

export default function AcceptInvitePage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { setCurrentOrgId } = useOrg();
  const accept = useAcceptInvitation();
  const started = useRef(false);

  const token = params.get("token");

  // mutate is intentionally fired once per mount; the ref guards StrictMode's
  // double-invoked effects.
  useEffect(() => {
    if (!token || started.current) return;
    started.current = true;
    accept.mutate(token, {
      onSuccess: (org) => {
        setCurrentOrgId(org.id);
        navigate(ROUTES.dashboard, { replace: true });
      },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <div
      data-testid="accept-invite-page"
      className="flex min-h-screen items-center justify-center bg-[var(--paper)] px-4"
    >
      <div className="w-full max-w-sm rounded border border-[var(--line)] bg-white p-8 text-center">
        {!token ? (
          <p data-testid="accept-invite-error" className="text-sm text-[var(--danger)]">
            This invitation link is missing its token.
          </p>
        ) : accept.error ? (
          <>
            <ErrorAlert error={accept.error} data-testid="accept-invite-error" />
            <Link
              data-testid="accept-invite-dashboard-button"
              to={ROUTES.dashboard}
              className="mt-4 inline-block text-sm text-[var(--teal-deep)] hover:underline"
            >
              Go to dashboard
            </Link>
          </>
        ) : (
          <p data-testid="accept-invite-loading" className="text-sm text-[var(--slate)]/75">
            Accepting invitation…
          </p>
        )}
      </div>
    </div>
  );
}
