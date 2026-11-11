import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { Alert, Button, Input, ErrorAlert } from "../../../shared/ui";
import { forgotPassword } from "../api/endpoints";
import { buildAuthPath, getDestinationLabel } from "../model/redirects";
import AuthSplitLayout from "./AuthSplitLayout";
import { EVENTS } from "../../../shared/lib/events";
import { track } from "../../../shared/lib/track";

export default function ForgotPasswordPage() {
  const [params] = useSearchParams();
  const requestedNext = params.get("next");
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const loginPath = buildAuthPath(ROUTES.auth.login, requestedNext);
  const destinationLabel = getDestinationLabel(requestedNext);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await forgotPassword(email);
      track(EVENTS.password_reset_requested); // never the email
      setSent(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthSplitLayout data-testid="forgot-password-page">
      <div className="border-b border-[var(--line)] pb-5">
        <p className="font-[family-name:var(--font-mono)] text-xs text-[var(--teal-deep)] tabular-nums">
          ACCOUNT RECOVERY
        </p>
        <h1 className="mt-2 font-[family-name:var(--font-display)] text-[30px] font-bold leading-[1.15] text-[var(--ink)]">
          Reset your password
        </h1>
        <p className="mt-2 text-sm leading-6 text-[var(--slate)]">
          We will send a reset link so you can continue to {destinationLabel}.
        </p>
      </div>

      {sent ? (
        <div className="mt-6 space-y-4">
          {/* Same copy whether or not the account exists — no enumeration. */}
          <Alert tone="success" data-testid="forgot-password-success">
            If an account exists for{" "}
            <span className="font-[family-name:var(--font-mono)] tabular-nums">{email}</span>, we
            have sent a password reset link. Check your inbox.
          </Alert>
          <Link
            to={loginPath}
            className="block w-full rounded border border-[var(--line)] px-3 py-2 text-center text-sm font-medium text-[var(--ink)] transition-colors hover:bg-[var(--mist)]/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--teal)]/30"
            data-testid="forgot-password-login-link"
          >
            Back to sign in
          </Link>
        </div>
      ) : (
        <>
          <form onSubmit={onSubmit} className="mt-6 space-y-4" data-testid="forgot-password-form">
            <Input
              id="forgot-password-email"
              label="Account email"
              type="email"
              required
              placeholder="Email"
              autoComplete="email"
              inputMode="email"
              autoFocus
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (error) setError(null);
              }}
              data-testid="forgot-password-email-input"
            />
            {!!error && <ErrorAlert error={error} data-testid="forgot-password-error" />}
            <Button
              type="submit"
              loading={busy}
              className="w-full"
              data-testid="forgot-password-submit"
            >
              Send reset link
            </Button>
          </form>
          <div className="mt-6 border-t border-[var(--line)] pt-4">
            <p className="text-sm text-[var(--slate)]">Remembered it?</p>
            <Link
              to={loginPath}
              className="mt-3 block w-full rounded border border-[var(--line)] px-3 py-2 text-center text-sm font-medium text-[var(--ink)] transition-colors hover:bg-[var(--mist)]/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--teal)]/30"
              data-testid="forgot-password-login-link"
            >
              Sign in
            </Link>
          </div>
        </>
      )}
    </AuthSplitLayout>
  );
}
