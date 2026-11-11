import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { getErrorMessage } from "../../../shared/api";
import { Alert, Button, Input, PasswordInput } from "../../../shared/ui";
import { buildAuthPath, getDestinationLabel, getSafeAuthRedirect } from "../model/redirects";
import { useAuth } from "../model/session";
import AuthSplitLayout from "./AuthSplitLayout";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const requestedNext = params.get("next");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const destinationLabel = getDestinationLabel(requestedNext);
  const forgotPasswordPath = buildAuthPath(ROUTES.auth.forgotPassword, requestedNext);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      navigate(getSafeAuthRedirect(requestedNext), { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthSplitLayout data-testid="login-page">
      <div className="border-b border-[var(--line)] pb-5">
        <p className="font-[family-name:var(--font-mono)] text-xs text-[var(--teal-deep)] tabular-nums">
          USER PORTAL
        </p>
        <h1
          id="login-heading"
          className="mt-2 font-[family-name:var(--font-display)] text-[30px] font-bold leading-[1.15] text-[var(--ink)]"
        >
          Sign in
        </h1>
        <p id="login-portal-note" className="mt-2 text-sm leading-6 text-[var(--slate)]">
          Use your account credentials to continue to {destinationLabel}.
        </p>
      </div>

      <form
        onSubmit={onSubmit}
        aria-labelledby="login-heading"
        aria-describedby={error ? "login-portal-note login-error" : "login-portal-note"}
        className="mt-6 space-y-4"
        data-testid="login-form"
      >
        <Input
          id="login-email"
          label="Email address"
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
          data-testid="login-email-input"
        />
        <PasswordInput
          id="login-password"
          label="Password"
          placeholder="Password"
          value={password}
          onChange={(value) => {
            setPassword(value);
            if (error) setError(null);
          }}
          show={showPassword}
          onToggle={() => setShowPassword((show) => !show)}
          autoComplete="current-password"
          data-testid="login-password-input"
        />
        <div className="flex items-center justify-between gap-4">
          <p className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--slate)] tabular-nums">
            SESSION / ORG
          </p>
          <Link
            to={forgotPasswordPath}
            className="text-sm font-medium text-[var(--teal-deep)] hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--teal)]/30"
            data-testid="login-forgot-link"
          >
            Forgot password?
          </Link>
        </div>
        {error && (
          <div id="login-error">
            <Alert tone="error" className="space-y-1" data-testid="login-error">
              <p className="font-medium text-[var(--ink)]">We could not sign you in.</p>
              <p>
                <span>{error}</span>{" "}
                <Link to={forgotPasswordPath} className="font-medium text-[var(--teal-deep)]">
                  Reset password
                </Link>
              </p>
            </Alert>
          </div>
        )}
        <Button type="submit" loading={busy} className="w-full" data-testid="login-submit">
          Sign in
        </Button>
      </form>

      <div className="mt-6 border-t border-[var(--line)] pt-4">
        <p className="text-sm text-[var(--slate)]">No account yet?</p>
        <Link
          to={buildAuthPath(ROUTES.auth.register, requestedNext)}
          className="mt-3 block w-full rounded border border-[var(--line)] px-3 py-2 text-center text-sm font-medium text-[var(--ink)] transition-colors hover:bg-[var(--mist)]/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--teal)]/30"
          data-testid="login-register-link"
        >
          Create account
        </Link>
      </div>
    </AuthSplitLayout>
  );
}
