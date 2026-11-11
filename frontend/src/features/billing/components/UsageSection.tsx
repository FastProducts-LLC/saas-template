import { useState, type CSSProperties } from "react";

import { Stamp } from "../../../shared/ui";
import {
  useClearMemberLimit,
  useCreditUsage,
  useSetMemberLimit,
  type CreditAction,
  type UsageActor,
} from "../../credits";

// Short mono labels for the per-actor action breakdown.
const ACTION_LABELS: Record<CreditAction, [singular: string, plural: string]> = {
  llm_call: ["LLM call", "LLM calls"],
  image_nano_banana: ["image", "images"],
  image_gpt: ["image", "images"],
  video_veo: ["video", "videos"],
};

function actionBreakdown(actor: UsageActor): string {
  return actor.actions
    .map((a) => {
      const label = ACTION_LABELS[a.action];
      return `${a.count} ${label ? label[a.count === 1 ? 0 : 1] : a.action}`;
    })
    .join(" · ");
}

/** Current month + the previous 5, newest first, as YYYY-MM. */
function recentPeriods(): string[] {
  const now = new Date();
  return Array.from({ length: 6 }, (_, i) => {
    const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - i, 1));
    return d.toISOString().slice(0, 7);
  });
}

function periodLabel(period: string): string {
  const [year, month] = period.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

function ActorCell({ actor }: { actor: UsageActor }) {
  if (actor.api_key_id !== null || actor.api_key_name !== null) {
    return (
      <div className="flex items-center gap-2">
        <span className="font-[family-name:var(--font-mono)] text-[var(--ink)]">
          {actor.api_key_name ?? "Deleted API key"}
        </span>
        <Stamp className="border-[var(--line)] text-[var(--slate)]/75">API key</Stamp>
      </div>
    );
  }
  if (actor.user_id === null && actor.user_email === null) {
    return <span className="text-[var(--slate)]/55">Removed member</span>;
  }
  return (
    <div>
      <span className="font-[family-name:var(--font-mono)] text-[var(--ink)]">
        {actor.user_email ?? "—"}
      </span>
      {actor.user_name && (
        <span className="block text-xs text-[var(--slate)]/65">{actor.user_name}</span>
      )}
    </div>
  );
}

function LimitCell({
  actor,
  orgId,
  admin,
  currentPeriod,
}: {
  actor: UsageActor;
  orgId: string;
  admin: boolean;
  currentPeriod: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const setLimit = useSetMemberLimit(orgId);
  const clearLimit = useClearMemberLimit(orgId);

  // Limits only apply to members (API keys spend against the org wallet).
  if (actor.user_id === null) {
    return <span className="text-[var(--slate)]/40">—</span>;
  }

  const canEdit = admin && currentPeriod;

  if (editing && canEdit) {
    const save = () => {
      const value = parseInt(draft, 10);
      if (Number.isFinite(value) && value >= 1) {
        setLimit.mutate({ userId: actor.user_id!, monthlyLimit: value });
      }
      setEditing(false);
    };
    return (
      <span className="inline-flex items-center gap-1.5">
        <input
          data-testid="usage-limit-input"
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value.replace(/[^0-9]/g, ""))}
          onKeyDown={(e) => {
            if (e.key === "Enter") save();
            if (e.key === "Escape") setEditing(false);
          }}
          aria-label="Monthly credit limit"
          className="w-20 rounded border border-[var(--line)] px-1.5 py-0.5 font-[family-name:var(--font-mono)] text-xs tabular-nums focus:border-[var(--teal)] focus:outline-none"
        />
        <button
          data-testid="usage-limit-save-button"
          onClick={save}
          className="text-xs text-[var(--teal-deep)] hover:underline"
        >
          Save
        </button>
        {actor.limit !== null && (
          <button
            data-testid="usage-limit-remove-button"
            onClick={() => {
              clearLimit.mutate(actor.user_id!);
              setEditing(false);
            }}
            className="text-xs text-[var(--slate)]/65 hover:underline"
          >
            Remove
          </button>
        )}
      </span>
    );
  }

  const startEdit = () => {
    setDraft(actor.limit !== null ? String(actor.limit) : "");
    setEditing(true);
  };

  if (actor.limit === null) {
    return canEdit ? (
      <button
        data-testid="usage-limit-edit-button"
        onClick={startEdit}
        className="text-xs text-[var(--slate)]/55 hover:text-[var(--teal-deep)] hover:underline"
      >
        Set limit
      </button>
    ) : (
      <span className="text-[var(--slate)]/40">—</span>
    );
  }

  const used = Math.min(actor.credits, actor.limit);
  const pct = Math.min(100, Math.round((actor.credits / actor.limit) * 100));
  return (
    <div className="min-w-[96px]">
      <button
        data-testid="usage-limit-edit-button"
        onClick={canEdit ? startEdit : undefined}
        className={`font-[family-name:var(--font-mono)] text-[13px] tabular-nums text-[var(--slate)] ${
          canEdit ? "hover:text-[var(--teal-deep)] hover:underline" : "cursor-default"
        }`}
        title={canEdit ? "Edit limit" : undefined}
      >
        {used.toLocaleString()} / {actor.limit.toLocaleString()}
      </button>
      <div className="mt-1 h-[2px] w-full bg-[var(--mist)]">
        <div className="h-full bg-[var(--teal)]" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function UsageSection({ orgId, admin }: { orgId: string; admin: boolean }) {
  const periods = recentPeriods();
  const [period, setPeriod] = useState(periods[0]);
  const { data: usage, isPending } = useCreditUsage(orgId, period);

  const hasLimits = admin || (usage?.items.some((a) => a.limit !== null) ?? false);
  const columns = hasLimits ? 4 : 3;

  return (
    <div
      data-testid="billing-usage"
      className="mt-3 overflow-hidden rounded border border-[var(--line)] bg-white"
    >
      <div className="flex items-center justify-between border-b border-[var(--line)] px-4 py-2.5">
        <h3 className="text-xs font-semibold text-[var(--ink)]">
          Credits by member
          {usage && (
            <span className="ml-2 font-[family-name:var(--font-mono)] font-normal tabular-nums text-[var(--slate)]/65">
              {usage.total_credits.toLocaleString()} spent
            </span>
          )}
        </h3>
        <select
          data-testid="usage-period-select"
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          aria-label="Usage period"
          className="rounded border border-[var(--line)] bg-white px-2 py-1 font-[family-name:var(--font-mono)] text-xs tabular-nums text-[var(--slate)] focus:border-[var(--teal)] focus:outline-none"
        >
          {periods.map((p) => (
            <option key={p} value={p}>
              {periodLabel(p)}
            </option>
          ))}
        </select>
      </div>
      <table data-testid="usage-table" className="w-full text-left">
        <thead>
          <tr className="h-10 bg-[var(--mist)] font-[family-name:var(--font-mono)] text-[11px] uppercase tracking-normal text-[var(--slate)]">
            <th className="px-4 py-2 font-medium">Member / key</th>
            <th className="px-4 py-2 font-medium">Actions</th>
            <th className="px-4 py-2 text-right font-medium">Credits</th>
            {hasLimits && <th className="px-4 py-2 font-medium">Limit</th>}
          </tr>
        </thead>
        <tbody>
          {usage?.items.map((actor, i) => (
            <tr
              key={`${actor.user_id ?? ""}:${actor.api_key_id ?? ""}`}
              data-testid="usage-row"
              data-id={`${actor.user_id ?? ""}:${actor.api_key_id ?? ""}`}
              className="gd-row-in h-10 border-t border-[var(--line)] text-[13px]"
              style={{ "--i": i } as CSSProperties}
            >
              <td className="px-4 py-2">
                <ActorCell actor={actor} />
              </td>
              <td className="px-4 py-2 font-[family-name:var(--font-mono)] text-[var(--slate)] tabular-nums">
                {actionBreakdown(actor) || "—"}
              </td>
              <td className="px-4 py-2 text-right font-[family-name:var(--font-mono)] font-medium tabular-nums text-[var(--ink)]">
                {actor.credits.toLocaleString()}
              </td>
              {hasLimits && (
                <td className="px-4 py-2">
                  <LimitCell
                    actor={actor}
                    orgId={orgId}
                    admin={admin}
                    currentPeriod={period === periods[0]}
                  />
                </td>
              )}
            </tr>
          ))}
          {usage && usage.items.length === 0 && (
            <tr data-testid="usage-empty" className="border-t border-[var(--line)]">
              <td
                colSpan={columns}
                className="px-4 py-8 text-center text-sm text-[var(--slate)]/55"
              >
                No usage in {periodLabel(period)}.
              </td>
            </tr>
          )}
          {isPending && !usage && (
            <tr data-testid="usage-loading" className="border-t border-[var(--line)]">
              <td
                colSpan={columns}
                className="px-4 py-8 text-center text-sm text-[var(--slate)]/40"
              >
                …
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
