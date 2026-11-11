import { useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { ApiError } from "../../shared/api";
import { Alert, Button, Input, Modal, ErrorAlert } from "../../shared/ui";
import { formatLimit, type Entitlement, type EntitlementKey } from "../entitlements";
import { useAdminEntitlements, useOverrideMutations } from "./api/entitlements-hooks";
import { validateOverride, localExpiry, type Override } from "./model/entitlements";
function OverrideEditor({
  orgId,
  entitlement,
  override,
}: {
  orgId: string;
  entitlement: Entitlement;
  override?: Override;
}) {
  const [limit, setLimit] = useState(String(override?.limit_value ?? entitlement.limit ?? ""));
  const [unlimited, setUnlimited] = useState(
    (override ? override.limit_value : entitlement.limit) === null,
  );
  const [expiry, setExpiry] = useState(localExpiry(override?.expires_at));
  const [note, setNote] = useState(override?.note ?? "");
  const [fields, setFields] = useState<Record<string, string>>({});
  const { save } = useOverrideMutations(orgId);
  function submit(event: FormEvent) {
    event.preventDefault();
    const errors = validateOverride(limit, unlimited, expiry, note);
    setFields(errors);
    if (Object.keys(errors).length) return;
    save.mutate(
      {
        key: entitlement.key,
        payload: {
          limit_value: unlimited ? null : Number(limit),
          expires_at: expiry ? new Date(expiry).toISOString() : null,
          note: note || null,
        },
      },
      {
        onError: (error) => {
          if (error instanceof ApiError) setFields(error.fields);
        },
      },
    );
  }
  return (
    <form
      onSubmit={submit}
      noValidate
      className="mt-4 space-y-3 border-t border-[var(--line)] py-4"
    >
      <h2 className="text-xl font-semibold">Set override: {entitlement.key}</h2>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={unlimited}
          onChange={(e) => setUnlimited(e.target.checked)}
        />
        Unlimited
      </label>
      <Input
        label="Limit"
        type="number"
        min="0"
        step="1"
        value={limit}
        disabled={unlimited}
        onChange={(e) => setLimit(e.target.value)}
        error={fields.limit_value}
        aria-invalid={!!fields.limit_value}
      />
      <Input
        label="Expiry (optional)"
        type="datetime-local"
        value={expiry}
        onChange={(e) => setExpiry(e.target.value)}
        error={fields.expires_at}
        aria-invalid={!!fields.expires_at}
      />
      <Input
        label="Note (optional)"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        error={fields.note}
        aria-invalid={!!fields.note}
      />
      {Object.keys(fields).length > 0 && (
        <Alert tone="error">Correct the highlighted fields before saving.</Alert>
      )}
      {save.error && <ErrorAlert error={save.error} />}
      {save.isSuccess && <Alert tone="success">Override saved.</Alert>}
      <Button type="submit" loading={save.isPending}>
        Save override
      </Button>
    </form>
  );
}
export default function AdminOrgEntitlementsPage() {
  const { orgId = "" } = useParams();
  const { data, isPending, error } = useAdminEntitlements(orgId);
  const [editing, setEditing] = useState<EntitlementKey | null>(null);
  const [removing, setRemoving] = useState<EntitlementKey | null>(null);
  const { remove } = useOverrideMutations(orgId);
  if (isPending) return <p role="status">Loading entitlements…</p>;
  if (error) return <ErrorAlert error={error} />;
  const selected = data.entitlements.find((item) => item.key === editing);
  return (
    <div>
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold">
        Organization entitlements
      </h1>
      <p className="mt-2">
        Plan: <span className="font-[family-name:var(--font-mono)]">{data.plan}</span>
      </p>
      <div className="mt-6 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-[var(--mist)]">
            <tr>
              {["Entitlement", "Effective limit", "Usage", "Source", "Actions"].map((label) => (
                <th key={label} className="px-4 py-2">
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="font-[family-name:var(--font-mono)] text-[13px] tabular-nums">
            {data.entitlements.map((item) => (
              <tr key={item.key} className="h-10 border-b border-[var(--line)]">
                <td className="px-4">{item.key}</td>
                <td className="px-4">{formatLimit(item.limit)}</td>
                <td className="px-4">{item.used}</td>
                <td className="px-4">{item.source}</td>
                <td className="space-x-2 px-4 font-[family-name:var(--font-body)]">
                  <Button
                    variant="secondary"
                    onClick={() => setEditing(item.key)}
                    aria-label={`Set override for ${item.key}`}
                  >
                    Set override
                  </Button>
                  {data.overrides.some((row) => row.key === item.key) && (
                    <Button
                      variant="secondary"
                      onClick={() => {
                        remove.reset();
                        setRemoving(item.key);
                      }}
                      aria-label={`Remove override for ${item.key}`}
                    >
                      Remove override
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selected && (
        <OverrideEditor
          key={`${orgId}-${selected.key}`}
          orgId={orgId}
          entitlement={selected}
          override={data.overrides.find((row) => row.key === selected.key)}
        />
      )}
      <Modal
        open={!!removing}
        onClose={() => {
          if (!remove.isPending) setRemoving(null);
        }}
        title="Remove override"
        footer={
          <>
            <Button
              variant="secondary"
              disabled={remove.isPending}
              onClick={() => setRemoving(null)}
            >
              Cancel
            </Button>
            <Button
              variant="danger-confirm"
              loading={remove.isPending}
              onClick={() => {
                if (removing)
                  remove.mutate(removing, {
                    onSuccess: () => {
                      setRemoving(null);
                      setEditing(null);
                    },
                  });
              }}
            >
              Confirm removal
            </Button>
          </>
        }
      >
        <p>Remove the {removing} override and restore the plan limit?</p>
        {remove.error && <ErrorAlert error={remove.error} />}
      </Modal>
    </div>
  );
}
