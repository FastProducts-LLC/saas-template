import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { clearStoredOrgId } from "../../../shared/lib/storage";
import {
  Button,
  ErrorAlert,
  Modal,
  PageHeader,
  SettingsList,
  SettingsSection,
} from "../../../shared/ui";
import { useDeleteOrg, useRenameOrg, useSetOrgDomain } from "../api/hooks";
import { useOrg } from "../model/current-org";
import { isAdmin, isOwner } from "../model/permissions";

export default function SettingsPage() {
  const { currentOrg } = useOrg();
  const navigate = useNavigate();
  const [name, setName] = useState(currentOrg!.name);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const [domain, setDomain] = useState(currentOrg!.email_domain ?? "");

  const rename = useRenameOrg();
  const deleteOrg = useDeleteOrg();
  const setOrgDomain = useSetOrgDomain();
  const error = rename.error ?? deleteOrg.error;

  const admin = isAdmin(currentOrg!.role);
  const owner = isOwner(currentOrg!.role);

  function onRename(e: FormEvent) {
    e.preventDefault();
    rename.mutate({ orgId: currentOrg!.id, name });
  }

  function onClaimDomain(e: FormEvent) {
    e.preventDefault();
    setOrgDomain.mutate({ orgId: currentOrg!.id, domain: domain.trim() });
  }

  function onReleaseDomain() {
    setOrgDomain.mutate(
      { orgId: currentOrg!.id, domain: null },
      { onSuccess: () => setDomain("") },
    );
  }

  function onDelete() {
    deleteOrg.mutate(currentOrg!.id, {
      onSuccess: () => {
        clearStoredOrgId();
        navigate(ROUTES.dashboard, { replace: true });
      },
    });
  }

  return (
    <div data-testid="org-settings-page" className="max-w-[1200px]">
      <div className="gd-stagger-item" style={{ "--i": 0 } as React.CSSProperties}>
        <PageHeader
          title="Settings"
          description={`How ${currentOrg!.name} is named, who can join, and what happens to it.`}
        />
      </div>

      <SettingsList className="gd-stagger-item mt-10">
        <SettingsSection
          title="Organization name"
          description="Shown to members, on invitations, and on invoices."
        >
          <form data-testid="org-settings-rename-form" onSubmit={onRename} className="flex gap-2">
            <input
              data-testid="org-settings-name-input"
              aria-label="Organization name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={!admin}
              className="min-w-0 flex-1 rounded border border-[var(--line)] px-3 py-2 text-sm text-[var(--ink)] transition-colors focus:border-[var(--teal)] focus:outline-none focus:ring-1 focus:ring-[var(--teal)]/20 disabled:bg-[var(--paper)]"
            />
            {admin && (
              <Button
                data-testid="org-settings-rename-submit"
                type="submit"
                disabled={rename.isPending}
              >
                Save
              </Button>
            )}
          </form>
          {rename.isSuccess && (
            <p data-testid="org-settings-success" className="mt-2 text-sm text-[var(--success)]">
              Saved.
            </p>
          )}
          {error && <ErrorAlert error={error} className="mt-2" data-testid="org-settings-error" />}
          <dl className="mt-4 flex items-center justify-between border-t border-[var(--line)] pt-3 text-[13px]">
            <dt className="text-[var(--slate)]">Slug</dt>
            <dd className="font-[family-name:var(--font-mono)] text-[var(--ink)]">
              {currentOrg!.slug}
            </dd>
          </dl>
        </SettingsSection>

        <SettingsSection
          title="Company domain"
          description={
            currentOrg!.email_domain
              ? `Anyone who verifies an @${currentOrg!.email_domain} email address joins automatically as a member.`
              : "Let people with your company email join automatically as members. Everyone else joins by invitation."
          }
        >
          {owner ? (
            <>
              <form
                data-testid="org-settings-domain-form"
                onSubmit={onClaimDomain}
                className="flex gap-2"
              >
                <input
                  data-testid="org-settings-domain-input"
                  aria-label="Company domain"
                  required
                  placeholder="acme.com"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  className="min-w-0 flex-1 rounded border border-[var(--line)] px-3 py-2 text-sm text-[var(--ink)] transition-colors focus:border-[var(--teal)] focus:outline-none focus:ring-1 focus:ring-[var(--teal)]/20"
                />
                <Button
                  data-testid="org-settings-domain-submit"
                  type="submit"
                  disabled={setOrgDomain.isPending}
                >
                  {currentOrg!.email_domain ? "Update" : "Claim"}
                </Button>
                {currentOrg!.email_domain && (
                  <Button
                    data-testid="org-settings-domain-remove-button"
                    variant="secondary"
                    onClick={onReleaseDomain}
                    disabled={setOrgDomain.isPending}
                  >
                    Remove
                  </Button>
                )}
              </form>
              <p className="mt-2 text-xs text-[var(--slate)]">
                The domain must match your own email address. Shared providers like gmail.com
                can&apos;t be claimed.
              </p>
              {setOrgDomain.isSuccess && (
                <p
                  data-testid="org-settings-domain-success"
                  className="mt-2 text-sm text-[var(--success)]"
                >
                  Saved.
                </p>
              )}
              {setOrgDomain.error && (
                <ErrorAlert
                  error={setOrgDomain.error}
                  className="mt-2"
                  data-testid="org-settings-domain-error"
                />
              )}
            </>
          ) : (
            <p className="font-[family-name:var(--font-mono)] text-sm text-[var(--ink)]">
              {currentOrg!.email_domain ?? "No domain claimed. Only an owner can claim one."}
            </p>
          )}
        </SettingsSection>

        {owner && (
          <SettingsSection
            tone="danger"
            title="Delete organization"
            description="Permanently removes its members, API keys, credits, and billing state. This cannot be undone."
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-[var(--slate)]">
                You&apos;ll be asked to confirm before anything is deleted.
              </p>
              <Button
                data-testid="org-settings-delete-button"
                variant="danger"
                onClick={() => setConfirmOpen(true)}
                disabled={deleteOrg.isPending}
                className="border border-[var(--danger)]/30"
              >
                Delete organization
              </Button>
            </div>
          </SettingsSection>
        )}
      </SettingsList>

      <Modal
        data-testid="org-settings-delete-modal"
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Delete organization"
        footer={
          <>
            <Button
              data-testid="org-settings-delete-cancel"
              variant="secondary"
              onClick={() => setConfirmOpen(false)}
            >
              Cancel
            </Button>
            <Button
              data-testid="org-settings-delete-confirm"
              variant="danger-confirm"
              loading={deleteOrg.isPending}
              onClick={onDelete}
            >
              Delete
            </Button>
          </>
        }
      >
        <p className="text-sm text-[var(--slate)]/75">
          Delete &ldquo;{currentOrg!.name}&rdquo; permanently? This cannot be undone.
        </p>
      </Modal>
    </div>
  );
}
