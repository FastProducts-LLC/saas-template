import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { EVENTS } from "../../../shared/lib/events";
import { track } from "../../../shared/lib/track";
import { ROUTES } from "../../../shared/lib/routes";
import { Alert, Button, Input, PasswordInput, ErrorAlert } from "../../../shared/ui";
import { passwordMeetsRules, validatePassword } from "../model/password-policy";
import { useAuth } from "../model/session";
import AuthSplitLayout from "./AuthSplitLayout";
import PasswordRules from "./PasswordRules";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [marketingOptIn, setMarketingOptIn] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [checkEmail, setCheckEmail] = useState(false);

  const firedStart = useRef(false);
  useEffect(() => {
    if (!firedStart.current) {
      firedStart.current = true;
      track(EVENTS.signup_started);
    }
  }, []);

  const rules = validatePassword(password);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!termsAccepted) {
      setError("You must accept the Terms of Service and Privacy Policy.");
      return;
    }
    if (!passwordMeetsRules(rules)) {
      setError("Password does not meet the requirements below.");
      return;
    }
    if (password !== passwordConfirmation) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      const verificationRequired = await register({
        first_name: firstName,
        last_name: lastName,
        email,
        password,
        password_confirmation: passwordConfirmation,
        terms_accepted: termsAccepted,
        marketing_opt_in: marketingOptIn,
      });
      if (verificationRequired) {
        setCheckEmail(true);
        return;
      }
      navigate(ROUTES.dashboard, { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (checkEmail) {
    return (
      <AuthSplitLayout data-testid="register-page">
        <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight text-[var(--ink)]">
          Check your email
        </h1>
        <div className="mt-6 space-y-4">
          {/* Same copy whether or not the address already had an account — no enumeration. */}
          <Alert tone="success" data-testid="register-check-email">
            We have sent an email to{" "}
            <span className="font-[family-name:var(--font-mono)] tabular-nums">{email}</span>. Open
            the link in it to finish, then sign in.
          </Alert>
          <Link
            to={ROUTES.auth.login}
            className="block w-full rounded border border-[var(--line)] px-3 py-2 text-center text-sm font-medium text-[var(--ink)] transition-colors hover:bg-[var(--mist)]/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--teal)]/30"
            data-testid="register-login-link"
          >
            Back to sign in
          </Link>
        </div>
      </AuthSplitLayout>
    );
  }

  return (
    <AuthSplitLayout data-testid="register-page">
      <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight text-[var(--ink)]">
        Create your account
      </h1>
      <p className="mt-1 text-sm text-[var(--slate)]/75">
        Start building in minutes — it's free to try.
      </p>
      <form onSubmit={onSubmit} className="mt-6 space-y-4" data-testid="register-form">
        <div className="flex gap-3">
          <input
            required
            placeholder="First name"
            aria-label="First name"
            value={firstName}
            autoComplete="given-name"
            onChange={(e) => setFirstName(e.target.value)}
            className="w-full rounded border border-[var(--line)] px-3 py-2 text-sm"
            data-testid="register-first-name-input"
          />
          <input
            placeholder="Last name"
            aria-label="Last name"
            value={lastName}
            autoComplete="family-name"
            onChange={(e) => setLastName(e.target.value)}
            className="w-full rounded border border-[var(--line)] px-3 py-2 text-sm"
            data-testid="register-last-name-input"
          />
        </div>
        <Input
          type="email"
          required
          placeholder="Email"
          aria-label="Email"
          value={email}
          autoComplete="email"
          onChange={(e) => setEmail(e.target.value)}
          data-testid="register-email-input"
        />
        <div className="space-y-2">
          <PasswordInput
            placeholder="Password"
            aria-label="Password"
            value={password}
            onChange={setPassword}
            show={showPassword}
            onToggle={() => setShowPassword((s) => !s)}
            autoComplete="new-password"
            data-testid="register-password-input"
          />
          {password.length > 0 && <PasswordRules rules={rules} />}
        </div>
        <div className="space-y-1">
          <PasswordInput
            placeholder="Confirm password"
            aria-label="Confirm password"
            value={passwordConfirmation}
            onChange={setPasswordConfirmation}
            show={showConfirm}
            onToggle={() => setShowConfirm((s) => !s)}
            autoComplete="new-password"
            data-testid="register-confirm-password-input"
          />
          {passwordConfirmation.length > 0 && password !== passwordConfirmation && (
            <p className="text-xs text-[var(--danger)]" data-testid="register-password-mismatch">
              Passwords do not match.
            </p>
          )}
        </div>

        <label className="flex items-start gap-2 text-sm text-[var(--slate)]">
          <input
            type="checkbox"
            checked={termsAccepted}
            onChange={(e) => {
              setTermsAccepted(e.target.checked);
              if (e.target.checked) setError(null);
            }}
            className="mt-0.5 h-4 w-4 rounded border-[var(--line)] text-[var(--teal-deep)]"
            data-testid="register-terms-checkbox"
          />
          <span>
            I agree to the{" "}
            <a
              href={ROUTES.legal.terms}
              target="_blank"
              rel="noreferrer"
              className="text-[var(--teal-deep)] hover:underline"
              data-testid="register-terms-link"
            >
              Terms of Service
            </a>{" "}
            and{" "}
            <a
              href={ROUTES.legal.privacy}
              target="_blank"
              rel="noreferrer"
              className="text-[var(--teal-deep)] hover:underline"
              data-testid="register-privacy-link"
            >
              Privacy Policy
            </a>
          </span>
        </label>
        <label className="flex items-start gap-2 text-sm text-[var(--slate)]">
          <input
            type="checkbox"
            checked={marketingOptIn}
            onChange={(e) => setMarketingOptIn(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-[var(--line)] text-[var(--teal-deep)]"
            data-testid="register-marketing-checkbox"
          />
          <span>Send me product updates, new features, and special offers (optional)</span>
        </label>

        {!!error && <ErrorAlert error={error} data-testid="register-error" />}
        <Button
          type="submit"
          disabled={busy || !termsAccepted}
          className="w-full"
          data-testid="register-submit"
        >
          {busy ? "Creating account…" : "Create Account"}
        </Button>
      </form>

      <div className="mt-4 flex items-center gap-3">
        <div className="h-px flex-1 bg-[var(--line)]" />
        <span className="text-xs text-[var(--slate)]/55">Already have an account?</span>
        <div className="h-px flex-1 bg-[var(--line)]" />
      </div>
      <Link
        to={ROUTES.auth.login}
        className="mt-4 block w-full rounded border border-[var(--line)] px-3 py-2 text-center text-sm font-medium text-[var(--slate)] hover:bg-[var(--paper)]"
        data-testid="register-login-link"
      >
        Sign In to Existing Account
      </Link>
    </AuthSplitLayout>
  );
}
