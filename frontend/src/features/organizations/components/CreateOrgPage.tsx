import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { isApiErrorWithCode } from "../../../shared/api";
import { ORG_INTENDED_USE_MAX_LENGTH, ORG_NAME_MAX_LENGTH } from "../../../shared/lib/policy";
import { Button, Input, ErrorAlert } from "../../../shared/ui";
import { useCreateOrg } from "../api/hooks";
import { useOrg } from "../model/current-org";

export default function CreateOrgPage() {
  const navigate = useNavigate();
  const { setCurrentOrgId } = useOrg();
  const [name, setName] = useState("");
  const [intendedUse, setIntendedUse] = useState("");
  const create = useCreateOrg();

  const domainOrgExists = isApiErrorWithCode(create.error, "ERR_ORG_007");

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    create.mutate(
      { name, intended_use: intendedUse },
      {
        onSuccess: (org) => {
          setCurrentOrgId(org.id);
          navigate(ROUTES.dashboard, { replace: true });
        },
      },
    );
  }

  return (
    <div
      data-testid="create-org-page"
      className="flex min-h-screen items-center justify-center bg-[var(--paper)] px-4"
    >
      <div className="w-full max-w-sm rounded border border-[var(--line)] bg-white p-8">
        <h1 className="text-xl font-semibold text-[var(--ink)]">Set up your company</h1>
        <p className="mt-1 text-sm text-[var(--slate)]/75">
          Your company workspace — invite teammates and manage billing here.
        </p>

        {domainOrgExists ? (
          <div data-testid="create-org-domain-exists" className="mt-6 space-y-4">
            <div className="rounded-lg border border-[var(--danger)] bg-transparent p-4">
              <p className="text-sm font-medium text-[var(--danger)]">
                Your company already has a workspace
              </p>
              <p className="mt-1 text-sm text-[var(--slate)]">
                Verify your email to join automatically, or ask the workspace owner for an
                invitation.
              </p>
            </div>
            <Button
              data-testid="create-org-verify-email-button"
              onClick={() => navigate(ROUTES.profile, { replace: true })}
              className="w-full"
            >
              Go to profile to verify email
            </Button>
          </div>
        ) : (
          <form data-testid="create-org-form" onSubmit={onSubmit} className="mt-6 space-y-4">
            <Input
              data-testid="create-org-name-input"
              required
              placeholder="Company name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={ORG_NAME_MAX_LENGTH}
            />
            <div className="space-y-1">
              <textarea
                data-testid="create-org-intended-use-input"
                required
                placeholder="How will you use this workspace? (e.g., internal tooling, customer-facing product, automation…)"
                value={intendedUse}
                onChange={(e) => setIntendedUse(e.target.value)}
                maxLength={ORG_INTENDED_USE_MAX_LENGTH}
                rows={3}
                className="w-full rounded border border-[var(--line)] px-3 py-2 text-sm placeholder:text-[var(--slate)]/50 focus:border-[var(--teal-deep)] focus:outline-none focus:ring-1 focus:ring-[var(--teal-deep)]"
              />
              <p className="text-right text-xs text-[var(--slate)]/50">
                {intendedUse.length}/{ORG_INTENDED_USE_MAX_LENGTH}
              </p>
            </div>
            {create.error && <ErrorAlert error={create.error} data-testid="create-org-error" />}
            <Button
              data-testid="create-org-submit"
              type="submit"
              loading={create.isPending}
              className="w-full"
            >
              {create.isPending ? "Creating…" : "Create company"}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
