import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { useEntitlements, isAtLimit, formatLimit, UpgradePrompt } from "../../entitlements";
import { BRAND_URL } from "../../../shared/lib/brand";
import { API_KEY_NAME_MAX_LENGTH, API_KEY_PREFIX } from "../../../shared/lib/policy";
import {
  Alert,
  Button,
  Card,
  CopyButton,
  Input,
  Modal,
  SectionRule,
  ErrorAlert,
  Meter,
  PageHeader,
} from "../../../shared/ui";
import { useOrg } from "../../organizations";
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from "../api/hooks";
import type { ApiKey } from "../model/types";

function CurlCopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      data-testid="api-keys-curl-copy"
      aria-label={copied ? "Copied" : "Copy"}
      title={copied ? "Copied" : "Copy"}
      className="inline-flex h-6 w-6 items-center justify-center rounded text-[var(--slate)] transition-colors hover:text-[var(--teal-deep)]"
    >
      {copied ? (
        <svg viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5" aria-hidden="true">
          <path
            d="M3 8.5 6.5 12 13 4.5"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ) : (
        <svg viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5" aria-hidden="true">
          <rect
            x="5.5"
            y="5.5"
            width="8"
            height="8"
            rx="1.5"
            stroke="currentColor"
            strokeWidth="1.4"
          />
          <path
            d="M10.5 5.5V4a1.5 1.5 0 0 0-1.5-1.5H4A1.5 1.5 0 0 0 2.5 4v5A1.5 1.5 0 0 0 4 10.5h1.5"
            stroke="currentColor"
            strokeWidth="1.4"
          />
        </svg>
      )}
    </button>
  );
}

function StepNumber({ n }: { n: number }) {
  return (
    <span className="shrink-0 font-[family-name:var(--font-mono)] text-xs text-[var(--slate)] tabular-nums">
      {String(n).padStart(2, "0")}
    </span>
  );
}

export default function ApiKeysPage() {
  const { currentOrg } = useOrg();
  const orgId = currentOrg!.id;
  const { data: keys, isLoading } = useApiKeys(orgId);
  const createKey = useCreateApiKey(orgId);
  const entitlements = useEntitlements(orgId);
  const entitlement = entitlements.data?.entitlements.find((item) => item.key === "api_keys");
  const atLimit = !!entitlement && isAtLimit(entitlement.limit, entitlement.used);
  const creationDisabled = atLimit;
  const revokeKey = useRevokeApiKey(orgId);

  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [newRawKey, setNewRawKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [revoking, setRevoking] = useState<ApiKey | null>(null);
  const [guideOpen, setGuideOpen] = useState(true);

  const hasKeys = keys && keys.length > 0;

  function handleCreate() {
    if (creationDisabled) return;
    createKey.mutate(
      { name },
      {
        onSuccess: (created) => {
          setNewRawKey(created.raw_key);
          setShowCreate(false);
          setName("");
        },
      },
    );
  }

  function handleCopy() {
    if (newRawKey) {
      navigator.clipboard.writeText(newRawKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  function handleRevoke() {
    if (!revoking) return;
    revokeKey.mutate(revoking.id, { onSuccess: () => setRevoking(null) });
  }

  const curlExample = `curl -sS "${BRAND_URL}/api/orgs/${orgId}/credits" \\
  -H "Authorization: Bearer ${API_KEY_PREFIX}YOUR_KEY"`;

  return (
    <div className="max-w-[1200px]" data-testid="api-keys-page">
      <PageHeader
        title="API keys"
        description={
          <>
            Keys let your own code call the API on behalf of this organization. Usage is billed to
            the organization and attributed to the key.{" "}
            <Link
              to={ROUTES.docs}
              data-testid="api-keys-docs-link"
              className="font-medium text-[var(--ink)] underline underline-offset-4"
            >
              API docs
            </Link>
            {" · "}
            <a
              href="/docs/api.md"
              data-testid="api-keys-md-link"
              className="font-medium text-[var(--ink)] underline underline-offset-4"
              target="_blank"
              rel="noreferrer"
            >
              api.md for LLMs
            </a>
          </>
        }
        actions={
          <Button
            onClick={() => setShowCreate(true)}
            disabled={showCreate || creationDisabled}
            data-testid="api-keys-create-button"
          >
            Create key
          </Button>
        }
      />

      {entitlement && (
        <div className="mt-6 max-w-sm">
          <p className="font-[family-name:var(--font-mono)] text-xs tabular-nums text-[var(--slate)]">
            {entitlement.used} of {formatLimit(entitlement.limit)} API keys used
          </p>
          {typeof entitlement.limit === "number" && entitlement.limit > 0 && (
            <Meter
              size="sm"
              className="mt-2"
              label={`${entitlement.used} of ${entitlement.limit} API keys used`}
              max={entitlement.limit}
              segments={[{ value: entitlement.used, className: "bg-[var(--ink)]" }]}
            />
          )}
        </div>
      )}
      {entitlements.isError && (
        <Alert tone="error" className="mt-4">
          Unable to load API key usage.
        </Alert>
      )}
      {atLimit && (
        <div className="mt-4">
          <UpgradePrompt entitlement="API keys" limit={entitlement!.limit} />
        </div>
      )}
      {/* ── New key banner ── */}
      {newRawKey && (
        <Alert tone="success" className="mt-6" data-testid="api-keys-success">
          <p className="font-medium">API key created — copy it now, you won't see it again.</p>
          <div className="mt-2 flex items-center gap-2">
            <code
              data-testid="api-keys-secret"
              className="flex-1 rounded border border-[var(--line)] bg-white px-3 py-2 font-[family-name:var(--font-mono)] text-sm text-[var(--ink)] break-all"
            >
              {newRawKey}
            </code>
            <Button onClick={handleCopy} className="shrink-0" data-testid="api-keys-secret-copy">
              {copied ? "Copied!" : "Copy"}
            </Button>
          </div>
          <button
            onClick={() => setNewRawKey(null)}
            data-testid="api-keys-dismiss-button"
            className="mt-2 text-xs text-[var(--teal-deep)] hover:underline"
          >
            I've saved it — dismiss
          </button>
        </Alert>
      )}

      {/* ── Your keys ── */}
      <SectionRule index="01" title="Your keys" className="mt-10" />

      {isLoading ? (
        <Card className="mt-4" data-testid="api-keys-loading">
          <div className="flex items-center gap-3 py-4">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--mist)] border-t-[var(--teal)]" />
            <span className="text-sm text-[var(--slate)]/75">Loading keys…</span>
          </div>
        </Card>
      ) : hasKeys ? (
        <div className="mt-4 overflow-hidden rounded border border-[var(--line)] bg-white">
          <table data-testid="api-keys-table" className="w-full text-left">
            <thead>
              <tr className="h-10 bg-[var(--mist)] font-[family-name:var(--font-mono)] text-[11px] uppercase tracking-normal text-[var(--slate)]">
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Key</th>
                <th className="px-4 py-2 font-medium">Created</th>
                <th className="px-4 py-2 text-right font-medium" />
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr
                  key={key.id}
                  data-testid="api-keys-row"
                  data-id={key.id}
                  className="h-10 border-t border-[var(--line)] text-[13px] hover:bg-[var(--paper)]"
                >
                  <td className="px-4 py-2 font-[family-name:var(--font-mono)] font-medium text-[var(--ink)]">
                    {key.name}
                  </td>
                  <td className="px-4 py-2">
                    <span className="inline-flex items-center gap-1.5">
                      <code className="rounded bg-[var(--paper)] px-2 py-0.5 font-[family-name:var(--font-mono)] text-[13px] text-[var(--slate)]">
                        {key.key_prefix}…
                      </code>
                      <CopyButton
                        value={key.key_prefix}
                        label="Copy key prefix"
                        data-testid="api-keys-prefix-copy"
                      />
                    </span>
                  </td>
                  <td className="px-4 py-2 font-[family-name:var(--font-mono)] text-[var(--slate)]/75 tabular-nums">
                    {new Date(key.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => setRevoking(key)}
                      data-testid="api-keys-revoke-button"
                      className="text-xs font-medium text-[var(--danger)] transition-colors hover:text-[var(--ink)]"
                    >
                      Revoke
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div
          data-testid="api-keys-empty"
          className="mt-4 rounded border border-dashed border-[var(--line)] bg-white py-8 text-center"
        >
          <p className="text-sm font-medium text-[var(--ink)]">No API keys yet</p>
          <p className="mx-auto mt-1 max-w-xs text-sm text-[var(--slate)]/65">
            Create a key to start querying records programmatically via the REST API.
          </p>
          <Button
            onClick={() => setShowCreate(true)}
            className="mt-4"
            data-testid="api-keys-empty-create-button"
          >
            Create your first key
          </Button>
        </div>
      )}

      {/* ── Quick start guide ── */}
      <SectionRule index="02" title="Quick start" className="mt-12" />

      <Card className="mt-4">
        <button
          type="button"
          onClick={() => setGuideOpen(!guideOpen)}
          data-testid="api-keys-guide-toggle"
          className="flex w-full items-center justify-between text-left"
        >
          <h3 className="text-sm font-semibold text-[var(--ink)]">Authenticate with your key</h3>
          <svg
            viewBox="0 0 20 20"
            fill="currentColor"
            className={`h-4 w-4 text-[var(--slate)]/50 transition-transform ${guideOpen ? "rotate-180" : ""}`}
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.168l3.71-3.938a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06Z"
              clipRule="evenodd"
            />
          </svg>
        </button>

        {guideOpen && (
          <div className="mt-4 space-y-4">
            <div className="flex items-start gap-3">
              <StepNumber n={1} />
              <div className="flex-1">
                <p className="text-sm text-[var(--ink)]">
                  Add an{" "}
                  <code className="rounded bg-[var(--paper)] px-1.5 py-0.5 font-[family-name:var(--font-mono)] text-xs text-[var(--ink)]">
                    Authorization
                  </code>{" "}
                  header to every request
                </p>
                <div className="mt-2 flex items-center gap-2 rounded border border-[var(--line)] bg-[var(--paper)] px-3 py-2">
                  <code className="flex-1 font-[family-name:var(--font-mono)] text-xs text-[var(--slate)]">
                    Authorization: Bearer {API_KEY_PREFIX}…
                  </code>
                  <CopyButton
                    value={`Authorization: Bearer ${API_KEY_PREFIX}YOUR_KEY`}
                    label="Copy header"
                    data-testid="api-keys-header-copy"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <StepNumber n={2} />
              <div className="flex-1">
                <p className="text-sm text-[var(--ink)]">
                  Use your organization id in the URL path
                </p>
                <div className="mt-2 flex items-center gap-2 rounded border border-[var(--line)] bg-[var(--paper)] px-3 py-2">
                  <code className="flex-1 truncate font-[family-name:var(--font-mono)] text-xs text-[var(--slate)]">
                    {orgId}
                  </code>
                  <CopyButton
                    value={orgId}
                    label="Copy org id"
                    data-testid="api-keys-org-id-copy"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <StepNumber n={3} />
              <div className="flex-1">
                <p className="text-sm text-[var(--ink)]">Try a sample request</p>
                <div className="relative mt-2 rounded border border-[var(--line)] bg-[var(--mist)] p-3 pr-10">
                  <pre className="overflow-x-auto font-[family-name:var(--font-mono)] text-[12px] leading-relaxed text-[var(--ink)]">
                    {curlExample}
                  </pre>
                  <div className="absolute right-2 top-2">
                    <CurlCopyButton value={curlExample} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* ── Create key modal ── */}
      <Modal
        open={showCreate}
        onClose={() => {
          setShowCreate(false);
          setName("");
        }}
        title="Create API Key"
        data-testid="api-keys-create-modal"
        footer={
          <>
            <Button
              variant="secondary"
              data-testid="api-keys-create-cancel"
              onClick={() => {
                setShowCreate(false);
                setName("");
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!name.trim() || creationDisabled}
              loading={createKey.isPending}
              data-testid="api-keys-create-confirm"
            >
              Create Key
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input
            label="Key name"
            placeholder="e.g. Production, Staging, CI"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={API_KEY_NAME_MAX_LENGTH}
            autoFocus
            data-testid="api-keys-name-input"
          />

          {createKey.error && <ErrorAlert error={createKey.error} data-testid="api-keys-error" />}
        </div>
      </Modal>

      {/* ── Revoke confirmation modal ── */}
      <Modal
        open={!!revoking}
        onClose={() => setRevoking(null)}
        title="Revoke API key"
        data-testid="api-keys-revoke-modal"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => setRevoking(null)}
              data-testid="api-keys-revoke-cancel"
            >
              Cancel
            </Button>
            <Button
              variant="danger-confirm"
              onClick={handleRevoke}
              loading={revokeKey.isPending}
              data-testid="api-keys-revoke-confirm"
            >
              Revoke Key
            </Button>
          </>
        }
      >
        <p className="text-sm text-[var(--slate)]">
          Are you sure you want to revoke{" "}
          <span className="font-[family-name:var(--font-mono)] font-medium text-[var(--ink)]">
            {revoking?.name}
          </span>
          ? Any integration using this key will immediately lose access. This cannot be undone.
        </p>
      </Modal>
    </div>
  );
}
