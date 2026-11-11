import { useState, type FormEvent } from "react";

import { Alert, ErrorAlert, Meter } from "../../../shared/ui";
import { useEntitlements, isAtLimit, UpgradePrompt, formatLimit } from "../../entitlements";
import { useInviteMember } from "../api/hooks";
import type { Role } from "../model/types";

export default function InviteForm({ orgId }: { orgId: string }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("member");
  const invite = useInviteMember(orgId);
  const entitlements = useEntitlements(orgId);
  const seats = entitlements.data?.entitlements.find((item) => item.key === "seats");
  const atLimit = !!seats && isAtLimit(seats.limit, seats.used);
  const disabled = atLimit || invite.isPending;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (disabled) return;
    invite.mutate({ email, role }, { onSuccess: () => setEmail("") });
  }

  const seatLimit = seats && typeof seats.limit === "number" ? seats.limit : null;

  return (
    <section
      aria-label="Invite a teammate"
      className="rounded border border-[var(--line)] bg-white p-5"
    >
      <h2 className="text-[15px] font-semibold text-[var(--ink)]">Invite a teammate</h2>
      <p className="mt-1 text-sm text-[var(--slate)]">
        They get an email with a link to join this organization.
      </p>
      {seats && (
        <div className="mt-4">
          <p className="font-[family-name:var(--font-mono)] text-xs tabular-nums text-[var(--slate)]">
            {seats.used} of {formatLimit(seats.limit)} seats used
          </p>
          {seatLimit !== null && seatLimit > 0 && (
            <Meter
              size="sm"
              className="mt-2"
              label={`${seats.used} of ${seatLimit} seats used`}
              max={seatLimit}
              segments={[{ value: seats.used, className: "bg-[var(--ink)]" }]}
            />
          )}
        </div>
      )}
      {entitlements.isError && (
        <Alert tone="error" className="mt-3">
          Unable to load seat usage.
        </Alert>
      )}
      {atLimit && (
        <div className="mt-3">
          <UpgradePrompt entitlement="Seats" limit={seats!.limit} />
        </div>
      )}
      {invite.error && (
        <ErrorAlert error={invite.error} className="mt-3" data-testid="invite-error" />
      )}
      <form data-testid="invite-form" onSubmit={onSubmit} className="mt-4 space-y-2">
        <input
          data-testid="invite-email-input"
          aria-label="Email"
          disabled={disabled}
          type="email"
          required
          placeholder="teammate@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded border border-[var(--line)] bg-white px-3 py-2 text-sm text-[var(--ink)] placeholder:text-[var(--slate)]/50 focus:border-[var(--teal)] focus:outline-none focus:ring-1 focus:ring-[var(--teal)] disabled:bg-[var(--paper)]"
        />
        <div className="flex gap-2">
          <select
            data-testid="invite-role-select"
            aria-label="Role"
            disabled={disabled}
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
            className="flex-1 rounded border border-[var(--line)] bg-white px-2 py-2 text-sm text-[var(--ink)] focus:border-[var(--teal)] focus:outline-none focus:ring-1 focus:ring-[var(--teal)]"
          >
            <option value="member">Member</option>
            <option value="admin">Admin</option>
          </select>
          <button
            data-testid="invite-submit"
            type="submit"
            disabled={disabled}
            className="rounded bg-[var(--ink)] px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--ink-soft)] disabled:opacity-50"
          >
            Invite
          </button>
        </div>
      </form>
    </section>
  );
}
