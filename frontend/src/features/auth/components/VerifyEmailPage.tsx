import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { useLinkToken } from "../../../shared/lib/linkToken";
import { AuthCard, ErrorAlert } from "../../../shared/ui";
import { verifyEmail } from "../api/endpoints";

type Status = "verifying" | "success" | "error";

export default function VerifyEmailPage() {
  const token = useLinkToken();
  const [status, setStatus] = useState<Status>(token ? "verifying" : "error");
  const [error, setError] = useState<unknown>(
    token ? null : "This verification link is missing its token.",
  );
  const requested = useRef(false);

  useEffect(() => {
    if (!token || requested.current) return;
    requested.current = true; // StrictMode double-mount guard
    verifyEmail(token)
      .then(() => setStatus("success"))
      .catch((err) => {
        setError(err);
        setStatus("error");
      });
  }, [token]);

  return (
    <AuthCard data-testid="verify-email-page">
      <h1 className="text-xl font-semibold text-[var(--ink)]">Email verification</h1>
      {status === "verifying" && (
        <p className="mt-6 text-sm text-[var(--slate)]" data-testid="verify-email-loading">
          Verifying your email address…
        </p>
      )}
      {status === "success" && (
        <div className="mt-6 space-y-4">
          <p className="text-sm text-[var(--slate)]" data-testid="verify-email-success">
            Your email address is verified — your account is fully activated.
          </p>
          <Link
            to={ROUTES.auth.login}
            className="inline-block rounded-lg bg-[var(--teal)] px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--teal-deep)]"
            data-testid="verify-email-login-link"
          >
            Continue to sign in
          </Link>
        </div>
      )}
      {status === "error" && (
        <div className="mt-6 space-y-4">
          <ErrorAlert error={error} data-testid="verify-email-error" />
          <p className="text-sm text-[var(--slate)]/75">
            Sign in and request a new verification email from your account.
          </p>
          <Link
            to={ROUTES.auth.login}
            className="text-sm text-[var(--teal-deep)] hover:underline"
            data-testid="verify-email-login-link"
          >
            Back to sign in
          </Link>
        </div>
      )}
    </AuthCard>
  );
}
