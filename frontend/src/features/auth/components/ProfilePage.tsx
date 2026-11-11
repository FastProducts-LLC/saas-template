import { useState, type FormEvent } from "react";

import { EVENTS } from "../../../shared/lib/events";
import { ACTIVITY_EVENT_RETENTION_DAYS } from "../../../shared/lib/policy";
import { track } from "../../../shared/lib/track";
import {
  Button,
  ErrorAlert,
  Input,
  PageHeader,
  SettingsList,
  SettingsSection,
  Stamp,
} from "../../../shared/ui";
import { openCookieSettings } from "../../consent";
import {
  changePassword,
  resendVerification,
  updateAnalyticsOptOut,
  updateMarketingOptIn,
  updateProfile,
} from "../api/endpoints";
import { passwordMeetsRules, validatePassword } from "../model/password-policy";
import { useAuth } from "../model/session";
import PasswordRules from "./PasswordRules";

function NameForm() {
  const { user, refreshUser } = useAuth();
  const [firstName, setFirstName] = useState(user?.first_name ?? "");
  const [lastName, setLastName] = useState(user?.last_name ?? "");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setStatus(null);
    setBusy(true);
    try {
      await updateProfile(firstName, lastName);
      track(EVENTS.settings_updated, { section: "profile_name" });
      await refreshUser();
      setStatus("Saved.");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" data-testid="profile-name-form">
      <div className="flex gap-3">
        <input
          required
          placeholder="First name"
          value={firstName}
          autoComplete="given-name"
          onChange={(e) => setFirstName(e.target.value)}
          className="w-full rounded border border-[var(--line)] px-3 py-2 text-sm transition-colors focus:border-[var(--teal)] focus:outline-none focus:ring-1 focus:ring-[var(--teal)]/20"
          data-testid="profile-first-name-input"
        />
        <input
          placeholder="Last name"
          value={lastName}
          autoComplete="family-name"
          onChange={(e) => setLastName(e.target.value)}
          className="w-full rounded border border-[var(--line)] px-3 py-2 text-sm transition-colors focus:border-[var(--teal)] focus:outline-none focus:ring-1 focus:ring-[var(--teal)]/20"
          data-testid="profile-last-name-input"
        />
      </div>
      {!!error && <ErrorAlert error={error} data-testid="profile-name-error" />}
      {status && (
        <p className="text-sm text-[var(--success)]" data-testid="profile-name-success">
          {status}
        </p>
      )}
      <Button type="submit" disabled={busy} data-testid="profile-name-submit">
        {busy ? "Saving…" : "Save name"}
      </Button>
    </form>
  );
}

function EmailSection() {
  const { user } = useAuth();
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function onResend() {
    setError(null);
    try {
      await resendVerification();
      setSent(true);
    } catch (err) {
      setError(err);
    }
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-[var(--ink)]" data-testid="profile-email">
        {user?.email}
      </p>
      {user?.email_verified ? (
        <Stamp className="border-[var(--success)] text-[var(--success)]">Verified</Stamp>
      ) : (
        <div className="flex items-center gap-3">
          <Stamp className="border-[var(--danger)] text-[var(--danger)]">Not verified</Stamp>
          {sent ? (
            <p className="text-sm text-[var(--slate)]/75" data-testid="profile-resend-success">
              Verification email sent — check your inbox.
            </p>
          ) : (
            <button
              onClick={onResend}
              className="text-sm text-[var(--teal-deep)] hover:underline"
              data-testid="profile-resend-button"
            >
              Resend verification email
            </button>
          )}
        </div>
      )}
      {!!error && <ErrorAlert error={error} data-testid="profile-email-error" />}
    </div>
  );
}

function PasswordForm() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const rules = validatePassword(password);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setStatus(null);
    if (!passwordMeetsRules(rules)) {
      setError("New password does not meet the requirements below.");
      return;
    }
    if (password !== confirmation) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await changePassword(currentPassword, password, confirmation);
      track(EVENTS.settings_updated, { section: "password" });
      setCurrentPassword("");
      setPassword("");
      setConfirmation("");
      setStatus("Password changed. Other devices have been signed out.");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" data-testid="profile-password-form">
      <Input
        type="password"
        required
        placeholder="Current password"
        value={currentPassword}
        autoComplete="current-password"
        onChange={(e) => setCurrentPassword(e.target.value)}
        data-testid="profile-current-password-input"
      />
      <div className="space-y-2">
        <Input
          type="password"
          required
          placeholder="New password"
          value={password}
          autoComplete="new-password"
          onChange={(e) => setPassword(e.target.value)}
          data-testid="profile-new-password-input"
        />
        {password.length > 0 && <PasswordRules rules={rules} />}
      </div>
      <Input
        type="password"
        required
        placeholder="Confirm new password"
        value={confirmation}
        autoComplete="new-password"
        onChange={(e) => setConfirmation(e.target.value)}
        data-testid="profile-confirm-password-input"
      />
      {!!error && <ErrorAlert error={error} data-testid="profile-password-error" />}
      {status && (
        <p className="text-sm text-[var(--success)]" data-testid="profile-password-success">
          {status}
        </p>
      )}
      <Button type="submit" disabled={busy} data-testid="profile-password-submit">
        {busy ? "Changing…" : "Change password"}
      </Button>
    </form>
  );
}

function MarketingToggle() {
  const { user, refreshUser } = useAuth();
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function onToggle(optIn: boolean) {
    setError(null);
    setBusy(true);
    try {
      await updateMarketingOptIn(optIn);
      track(EVENTS.settings_updated, { section: "marketing" });
      await refreshUser();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <label className="flex items-start gap-2 text-sm text-[var(--slate)]">
        <input
          type="checkbox"
          checked={user?.marketing_opt_in ?? false}
          disabled={busy}
          onChange={(e) => onToggle(e.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-[var(--line)] accent-[var(--teal-deep)]"
          data-testid="profile-marketing-checkbox"
        />
        <span>Send me product updates, new features, and special offers</span>
      </label>
      {!!error && (
        <ErrorAlert error={error} className="mt-2" data-testid="profile-marketing-error" />
      )}
    </div>
  );
}

/** Account-level objection to product analytics (GDPR Art. 21). Independent
 *  of the cookie banner: that governs the Google Analytics tag on this
 *  device; this stops first-party usage records AND Google Analytics for the
 *  account, everywhere. Deliberately fires no analytics event of its own. */
function AnalyticsToggle() {
  const { user, refreshUser } = useAuth();
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function onToggle(share: boolean) {
    setError(null);
    setBusy(true);
    try {
      await updateAnalyticsOptOut(!share);
      await refreshUser(); // re-identifies, which applies the new setting at once
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-4">
      <label className="flex items-start gap-2 text-sm text-[var(--slate)]">
        <input
          type="checkbox"
          checked={!(user?.analytics_opt_out ?? false)}
          disabled={busy}
          onChange={(e) => onToggle(e.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-[var(--line)] accent-[var(--teal-deep)]"
          data-testid="profile-analytics-checkbox"
        />
        <span>
          Help improve the product with usage analytics
          <span className="mt-1 block text-xs text-[var(--slate)]">
            We record which features your account uses (never what you type or create) and keep it
            for {Math.round(ACTIVITY_EVENT_RETENTION_DAYS / 365)} years. Turn this off to stop
            recording for your account on every device.
          </span>
        </span>
      </label>
      {!!error && (
        <ErrorAlert error={error} className="mt-2" data-testid="profile-analytics-error" />
      )}
    </div>
  );
}

export default function ProfilePage() {
  return (
    <div className="max-w-[1200px]" data-testid="profile-page">
      <div className="gd-stagger-item" style={{ "--i": 0 } as React.CSSProperties}>
        <PageHeader
          title="Profile"
          description="Your personal account. These settings follow you across every organization."
        />
      </div>

      <SettingsList className="gd-stagger-item mt-10">
        <SettingsSection
          data-testid="profile-name-section"
          title="Name"
          description="How you appear to teammates and in the member directory."
        >
          <NameForm />
        </SettingsSection>

        <SettingsSection
          data-testid="profile-email-section"
          title="Email"
          description="Used to sign in and for account notices."
        >
          <EmailSection />
        </SettingsSection>

        <SettingsSection
          data-testid="profile-password-section"
          title="Password"
          description="Changing it signs out your other sessions."
        >
          <PasswordForm />
        </SettingsSection>

        <SettingsSection
          data-testid="profile-marketing-section"
          title="Email preferences"
          description="Product news is optional. Account and billing emails are always sent."
        >
          <MarketingToggle />
        </SettingsSection>

        <SettingsSection
          data-testid="profile-privacy-section"
          title="Privacy"
          description="Manage the optional cookies this site may use. Your choice is kept on this device and recorded to your account."
        >
          <button
            type="button"
            onClick={openCookieSettings}
            data-testid="profile-cookie-settings-button"
            className="text-sm font-medium text-[var(--ink)] underline-offset-4 hover:underline"
          >
            Cookie settings
          </button>
          <AnalyticsToggle />
        </SettingsSection>
      </SettingsList>
    </div>
  );
}
