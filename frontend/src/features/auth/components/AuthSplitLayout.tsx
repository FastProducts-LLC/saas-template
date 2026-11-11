// Split-screen shell for the auth pages: operational context on the left,
// form content on the right. The panel collapses below lg, leaving the form
// full-width with a small logo on top.

import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { AUTH_PANEL_CONTENT } from "../../../shared/content/marketing";
import { BRAND, BRAND_LEGAL } from "../../../shared/lib/brand";
import keysArt from "../../../shared/assets/art/feature-keys.webp";
import { Art } from "../../../shared/ui/marketing";

const accessRowTones = [
  "text-[var(--teal-deep)] border-[var(--teal-deep)]",
  "text-[var(--info)] border-[var(--info)]",
  "text-[var(--slate)] border-[var(--line)]",
];

export default function AuthSplitLayout({
  children,
  "data-testid": testId,
}: {
  children: ReactNode;
  "data-testid"?: string;
}) {
  return (
    <div className="flex min-h-screen bg-white" data-testid={testId}>
      <div className="relative hidden w-1/2 flex-col justify-between overflow-hidden border-r border-[var(--sand-line)] bg-[var(--sand)] p-12 lg:flex">
        <div
          className="mk-dots pointer-events-none absolute inset-0 opacity-70"
          aria-hidden="true"
        />
        {/* Series artwork (DESIGN.md "Artwork"): a key for the way in. */}
        <div className="pointer-events-none absolute right-6 top-16 hidden h-[230px] w-[280px] xl:block">
          <div className="mk-glow absolute left-1/2 top-1/2 h-[220px] w-[220px] -translate-x-1/2 -translate-y-1/2" />
          <Art
            src={keysArt}
            width={1200}
            height={800}
            priority
            className="relative h-full w-full object-cover"
          />
        </div>

        <div className="relative flex items-center justify-between gap-6">
          <Link
            to={ROUTES.home}
            className="font-[family-name:var(--font-display)] text-xl font-bold text-[var(--ink)]"
            data-testid="auth-home-link"
          >
            {BRAND}
          </Link>
          <span className="font-[family-name:var(--font-mono)] text-xs text-[var(--slate)] tabular-nums">
            {AUTH_PANEL_CONTENT.entryLabel}
          </span>
        </div>

        <div className="relative">
          <p className="font-[family-name:var(--font-mono)] text-xs text-[var(--teal-deep)] tabular-nums">
            {AUTH_PANEL_CONTENT.eyebrow}
          </p>
          <h2 className="mt-3 max-w-md font-[family-name:var(--font-display)] text-[40px] leading-[1.1] text-[var(--ink)]">
            {AUTH_PANEL_CONTENT.headline}
          </h2>
          <p className="mt-4 max-w-md text-sm leading-6 text-[var(--slate)]">
            {AUTH_PANEL_CONTENT.blurb}
          </p>

          <div className="mt-10 rounded-lg border border-[var(--sand-line)] bg-white shadow-sm">
            <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-b border-[var(--line)] px-4 py-3">
              <p className="text-sm font-semibold text-[var(--ink)]">
                {AUTH_PANEL_CONTENT.accessHeading}
              </p>
              <span className="rounded-[2px] border border-[var(--teal-deep)] px-1.5 py-0.5 font-[family-name:var(--font-mono)] text-[11px] font-medium text-[var(--teal-deep)]">
                {AUTH_PANEL_CONTENT.status}
              </span>
            </div>
            {AUTH_PANEL_CONTENT.accessRows.map((row, i) => (
              <div
                key={row.label}
                className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-b border-[var(--line)] px-4 py-3 last:border-b-0"
              >
                <span className="text-sm text-[var(--slate)]">{row.label}</span>
                <span
                  className={`rounded-[2px] border px-1.5 py-0.5 font-[family-name:var(--font-mono)] text-[11px] font-medium uppercase ${accessRowTones[i]}`}
                >
                  {row.value}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="relative grid grid-cols-3 border-t border-[var(--line)] pt-5">
          <div>
            <p className="font-[family-name:var(--font-mono)] text-xs text-[var(--ink)] tabular-nums">
              01
            </p>
            <p className="mt-1 text-xs text-[var(--slate)]">{AUTH_PANEL_CONTENT.capabilities[0]}</p>
          </div>
          <div className="border-l border-[var(--line)] pl-5">
            <p className="font-[family-name:var(--font-mono)] text-xs text-[var(--ink)] tabular-nums">
              02
            </p>
            <p className="mt-1 text-xs text-[var(--slate)]">{AUTH_PANEL_CONTENT.capabilities[1]}</p>
          </div>
          <div className="border-l border-[var(--line)] pl-5">
            <p className="font-[family-name:var(--font-mono)] text-xs text-[var(--ink)] tabular-nums">
              03
            </p>
            <p className="mt-1 text-xs text-[var(--slate)]">{AUTH_PANEL_CONTENT.capabilities[2]}</p>
          </div>
          <p className="col-span-3 mt-8 text-sm text-[var(--slate)]/60">
            © {new Date().getFullYear()} {BRAND_LEGAL}
          </p>
        </div>
      </div>

      <div className="flex flex-1 flex-col justify-center px-4 pb-48 pt-8 sm:px-6 sm:py-8 lg:px-12">
        <div className="mx-auto w-full max-w-sm">
          <Link
            to={ROUTES.home}
            className="mb-8 block font-[family-name:var(--font-display)] text-lg font-bold tracking-tight text-[var(--ink)] lg:hidden"
            data-testid="auth-home-link-mobile"
          >
            {BRAND}
          </Link>
          {children}
        </div>
      </div>
    </div>
  );
}
