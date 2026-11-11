import { type ReactNode } from "react";

interface SettingsSectionProps {
  title: string;
  description?: ReactNode;
  children: ReactNode;
  tone?: "default" | "danger";
  "data-testid"?: string;
}

// Two-column settings row: what the setting is (left) and the control
// (right). Rows are divided by hairlines; on narrow screens they stack.
// Use inside <SettingsList> so the first row has no top rule.
export function SettingsSection({
  title,
  description,
  children,
  tone = "default",
  "data-testid": testId,
}: SettingsSectionProps) {
  return (
    <section
      data-testid={testId}
      className="grid gap-4 py-8 first:pt-0 last:pb-0 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] lg:gap-12"
    >
      <div>
        <h2
          className={`text-[15px] font-semibold ${
            tone === "danger" ? "text-[var(--danger)]" : "text-[var(--ink)]"
          }`}
        >
          {title}
        </h2>
        {description && (
          <p className="mt-1 text-sm leading-relaxed text-[var(--slate)]">{description}</p>
        )}
      </div>
      <div
        className={`rounded border bg-white p-5 ${
          tone === "danger" ? "border-[var(--danger)]/30" : "border-[var(--line)]"
        }`}
      >
        {children}
      </div>
    </section>
  );
}

export function SettingsList({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`divide-y divide-[var(--line)] ${className}`}>{children}</div>;
}
