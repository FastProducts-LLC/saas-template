import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { useLinkToken } from "../../../shared/lib/linkToken";
import { Alert, Button, PasswordInput, ErrorAlert } from "../../../shared/ui";
import { resetPassword } from "../api/endpoints";
import { passwordMeetsRules, validatePassword } from "../model/password-policy";
import { buildAuthPath } from "../model/redirects";
import AuthSplitLayout from "./AuthSplitLayout";
import PasswordRules from "./PasswordRules";

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = useLinkToken();
  const requestedNext = params.get("next");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const rules = validatePassword(password);
  const loginPath = buildAuthPath(ROUTES.auth.login, requestedNext);
  const forgotPasswordPath = buildAuthPath(ROUTES.auth.forgotPassword, requestedNext);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!passwordMeetsRules(rules)) {
      setError("Password does not meet the requirements below.");
      return;
    }
    if (password !== confirmation) {
      setError("The two passwords you entered don't match.");
      return;
    }
    setBusy(true);
    try {
      await resetPassword(token, password, confirmation);
      setDone(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthSplitLayout data-testid="reset-password-page">
      <div className="border-b border-[var(--line)] pb-5">
        <p className="font-[family-name:var(--font-mono)] text-xs text-[var(--teal-deep)] tabular-nums">
          PASSWORD RESET
        </p>
        <h1 className="mt-2 font-[family-name:var(--font-display)] text-[30px] font-bold leading-[1.15] text-[var(--ink)]">
          Choose a new password
        </h1>
        <p className="mt-2 text-sm leading-6 text-[var(--slate)]">
          Set a fresh password. Existing sessions will be revoked after this change.
        </p>
      </div>

      {!token ? (
        <div className="mt-6 space-y-4">
          <Alert tone="error" data-testid="reset-password-error">
            This reset link is missing its token. Request a new one and use the full link from the
            email.
          </Alert>
          <Link
            to={forgotPasswordPath}
            className="block w-full rounded border border-[var(--line)] px-3 py-2 text-center text-sm font-medium text-[var(--ink)] transition-colors hover:bg-[var(--mist)]/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--teal)]/30"
            data-testid="reset-password-forgot-link"
          >
            Request a new link
          </Link>
        </div>
      ) : done ? (
        <div className="mt-6 space-y-4">
          <Alert tone="success" data-testid="reset-password-success">
            Your password has been updated and you've been signed out everywhere.
          </Alert>
          <Link
            to={loginPath}
            className="block w-full rounded bg-[var(--ink)] px-3 py-2 text-center text-sm font-semibold text-white transition-colors hover:bg-[var(--ink-soft)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--teal)]/30"
            data-testid="reset-password-login-link"
          >
            Sign in with your new password
          </Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="mt-6 space-y-4" data-testid="reset-password-form">
          <div className="space-y-2">
            <PasswordInput
              id="reset-password-password"
              label="New password"
              placeholder="New password"
              value={password}
              onChange={(value) => {
                setPassword(value);
                if (error) setError(null);
              }}
              show={showPassword}
              onToggle={() => setShowPassword((show) => !show)}
              showLabel="Show new password"
              hideLabel="Hide new password"
              autoComplete="new-password"
              data-testid="reset-password-password-input"
            />
            {password.length > 0 && <PasswordRules rules={rules} />}
          </div>
          <PasswordInput
            id="reset-password-confirmation"
            label="Confirm new password"
            placeholder="Confirm new password"
            value={confirmation}
            onChange={(value) => {
              setConfirmation(value);
              if (error) setError(null);
            }}
            show={showConfirmation}
            onToggle={() => setShowConfirmation((show) => !show)}
            showLabel="Show password confirmation"
            hideLabel="Hide password confirmation"
            autoComplete="new-password"
            error={
              confirmation.length > 0 && password !== confirmation
                ? "Passwords do not match."
                : undefined
            }
            data-testid="reset-password-confirm-password-input"
          />
          {!!error && (
            <div className="space-y-1">
              <ErrorAlert error={error} data-testid="reset-password-error" />
              <Link
                to={forgotPasswordPath}
                className="text-sm text-[var(--teal-deep)] hover:underline"
                data-testid="reset-password-forgot-link"
              >
                Request a new link
              </Link>
            </div>
          )}
          <Button
            type="submit"
            loading={busy}
            className="w-full"
            data-testid="reset-password-submit"
          >
            Set new password
          </Button>
        </form>
      )}
    </AuthSplitLayout>
  );
}
