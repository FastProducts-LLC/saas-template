import { Fragment, useMemo, useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { SectionRule, Stamp } from "../../../shared/ui";
import {
  countSaasFeatures,
  saasBuildPhases,
  saasFeatureCatalog,
  type SaasFeature,
  type SaasFeatureArea,
  type SaasFeatureStatus,
} from "../model/featureCatalog";

const statusLabel: Record<SaasFeatureStatus, string> = {
  included: "Included",
  blueprint: "Blueprint",
};

const statusStyle: Record<SaasFeatureStatus, string> = {
  included: "border-[var(--success)] text-[var(--success)]",
  blueprint: "border-[var(--info)] text-[var(--info)]",
};

const areas: Array<"all" | SaasFeatureArea> = [
  "all",
  "Access",
  "Admin",
  "Billing",
  "Developer",
  "Growth",
  "Operations",
  "Platform",
  "Trust",
];

const statusFilters: Array<"all" | SaasFeatureStatus> = ["all", "included", "blueprint"];

const implementationSections: Array<{
  key: keyof SaasFeature["implementation"];
  label: string;
}> = [
  { key: "database", label: "Data model" },
  { key: "backend", label: "Backend" },
  { key: "frontend", label: "Frontend" },
  { key: "verification", label: "Verification" },
];

function searchableText(feature: SaasFeature): string {
  return [
    feature.title,
    feature.area,
    feature.summary,
    feature.templateFit,
    feature.nextStep,
    ...feature.implementation.database,
    ...feature.implementation.backend,
    ...feature.implementation.frontend,
    ...feature.implementation.verification,
  ]
    .join(" ")
    .toLowerCase();
}

function SummaryBlock({
  label,
  value,
  index,
}: {
  label: string;
  value: string | number;
  index: number;
}) {
  return (
    <div
      className={`px-5 py-4 ${index > 0 ? "border-t border-[var(--line)] sm:border-l sm:border-t-0" : ""}`}
    >
      <p className="font-[family-name:var(--font-display)] text-[34px] font-bold leading-none text-[var(--ink)] tabular-nums">
        {value}
      </p>
      <p className="mt-2 text-sm text-[var(--slate)]">{label}</p>
    </div>
  );
}

export default function SaasFeaturesPage() {
  const [status, setStatus] = useState<"all" | SaasFeatureStatus>("all");
  const [area, setArea] = useState<"all" | SaasFeatureArea>("all");
  const [query, setQuery] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>("notifications");

  const featureById = useMemo(
    () => new Map(saasFeatureCatalog.map((feature) => [feature.id, feature])),
    [],
  );

  const visibleFeatures = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return saasFeatureCatalog.filter((feature) => {
      const matchesStatus = status === "all" || feature.status === status;
      const matchesArea = area === "all" || feature.area === area;
      const matchesQuery = !normalized || searchableText(feature).includes(normalized);
      return matchesStatus && matchesArea && matchesQuery;
    });
  }, [area, query, status]);

  return (
    <div className="max-w-[1200px]" data-testid="saas-features-page">
      <div className="gd-stagger-item" style={{ "--i": 0 } as CSSProperties}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-[var(--ink)]">
              SaaS Essentials
            </h1>
            <p className="mt-1 max-w-3xl text-sm text-[var(--slate)]/75">
              A {countSaasFeatures()}-feature map for turning this template into a production SaaS.
              Included items already have working surfaces; blueprints are the next reusable slices
              to add.
            </p>
          </div>
          <Link
            to={ROUTES.docs}
            data-testid="saas-features-docs-link"
            className="gd-press inline-flex items-center gap-2 self-start rounded bg-[var(--ink)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--ink-soft)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--teal)]/30 lg:self-auto"
          >
            API docs
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4"
              aria-hidden="true"
            >
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </Link>
        </div>
      </div>

      <div
        data-testid="saas-features-summary"
        className="gd-stagger-item mt-5 border-t border-[var(--line)]"
        style={{ "--i": 1 } as CSSProperties}
      >
        <div className="grid grid-cols-1 sm:grid-cols-4">
          <SummaryBlock index={0} label="Top features" value={countSaasFeatures()} />
          <SummaryBlock index={1} label="Already included" value={countSaasFeatures("included")} />
          <SummaryBlock
            index={2}
            label="Blueprints to build"
            value={countSaasFeatures("blueprint")}
          />
          <SummaryBlock index={3} label="Priority baseline" value="P0-P2" />
        </div>
      </div>

      <SectionRule index="01" title="Recommended build sequence" className="mt-8" />

      <div
        className="gd-stagger-item mt-3 overflow-hidden rounded border border-[var(--line)] bg-white"
        style={{ "--i": 2 } as CSSProperties}
      >
        <div className="grid divide-y divide-[var(--line)] lg:grid-cols-4 lg:divide-x lg:divide-y-0">
          {saasBuildPhases.map((phase, index) => (
            <section key={phase.id} data-testid="saas-build-phase" className="p-4">
              <p className="font-[family-name:var(--font-mono)] text-xs text-[var(--slate)] tabular-nums">
                {String(index + 1).padStart(2, "0")}
              </p>
              <h2 className="mt-2 text-sm font-semibold text-[var(--ink)]">{phase.title}</h2>
              <p className="mt-2 text-sm leading-5 text-[var(--slate)]/75">{phase.outcome}</p>
              <ul className="mt-3 space-y-1">
                {phase.featureIds.map((featureId) => {
                  const feature = featureById.get(featureId);
                  if (!feature) return null;
                  return (
                    <li key={featureId} className="flex items-center gap-2 text-xs">
                      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--teal)]" />
                      <button
                        type="button"
                        onClick={() => setExpandedId(featureId)}
                        className="truncate text-left text-[var(--teal-deep)] hover:underline"
                      >
                        {feature.title}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      </div>

      <div
        className="gd-stagger-item mt-7 rounded border border-[var(--line)] bg-white p-4"
        style={{ "--i": 3 } as CSSProperties}
      >
        <div className="grid gap-3 lg:grid-cols-[1fr_auto_auto] lg:items-end">
          <label className="block">
            <span className="text-xs font-medium text-[var(--slate)]">Search</span>
            <input
              data-testid="saas-features-search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search features, slices, or outcomes"
              className="mt-1 w-full rounded border border-[var(--line)] px-3 py-2 text-sm text-[var(--ink)] transition-colors focus:border-[var(--teal)] focus:outline-none focus:ring-1 focus:ring-[var(--teal)]/20"
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-[var(--slate)]">Status</span>
            <select
              data-testid="saas-features-status-filter"
              value={status}
              onChange={(event) => setStatus(event.target.value as "all" | SaasFeatureStatus)}
              className="mt-1 w-full rounded border border-[var(--line)] bg-white px-3 py-2 text-sm text-[var(--ink)] focus:border-[var(--teal)] focus:outline-none focus:ring-1 focus:ring-[var(--teal)]/20 lg:w-40"
            >
              {statusFilters.map((item) => (
                <option key={item} value={item}>
                  {item === "all" ? "All status" : statusLabel[item]}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-medium text-[var(--slate)]">Area</span>
            <select
              data-testid="saas-features-area-filter"
              value={area}
              onChange={(event) => setArea(event.target.value as "all" | SaasFeatureArea)}
              className="mt-1 w-full rounded border border-[var(--line)] bg-white px-3 py-2 text-sm text-[var(--ink)] focus:border-[var(--teal)] focus:outline-none focus:ring-1 focus:ring-[var(--teal)]/20 lg:w-44"
            >
              {areas.map((item) => (
                <option key={item} value={item}>
                  {item === "all" ? "All areas" : item}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <SectionRule
        index="02"
        title={`Top ${countSaasFeatures()} generalized SaaS features`}
        className="mt-8"
      />

      <div
        className="gd-stagger-item mt-3 overflow-hidden rounded border border-[var(--line)] bg-white"
        style={{ "--i": 4 } as CSSProperties}
      >
        <table data-testid="saas-features-table" className="w-full table-fixed text-left">
          <thead>
            <tr className="h-10 bg-[var(--mist)] font-[family-name:var(--font-mono)] text-[11px] uppercase tracking-normal text-[var(--slate)]">
              <th className="w-[30%] px-4 py-2 font-medium">Feature</th>
              <th className="hidden w-24 px-4 py-2 font-medium md:table-cell">Area</th>
              <th className="w-28 px-4 py-2 font-medium">Status</th>
              <th className="hidden w-24 px-4 py-2 font-medium lg:table-cell">Priority</th>
              <th className="px-4 py-2 font-medium">Next step</th>
            </tr>
          </thead>
          <tbody>
            {visibleFeatures.map((feature, index) => (
              <Fragment key={feature.id}>
                <tr
                  data-testid="saas-feature-row"
                  data-id={feature.id}
                  className="gd-row-in border-t border-[var(--line)] align-top text-[13px] transition-colors hover:bg-[var(--paper)]"
                  style={{ "--i": index } as CSSProperties}
                >
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-1">
                      {feature.route ? (
                        <Link
                          to={feature.route}
                          className="font-semibold text-[var(--ink)] hover:text-[var(--teal-deep)] hover:underline"
                        >
                          {feature.title}
                        </Link>
                      ) : (
                        <span className="font-semibold text-[var(--ink)]">{feature.title}</span>
                      )}
                      <span className="text-sm leading-5 text-[var(--slate)]/75">
                        {feature.summary}
                      </span>
                      <span className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--slate)]/55 md:hidden">
                        {feature.area} / {feature.priority} / effort {feature.effort}
                      </span>
                    </div>
                  </td>
                  <td className="hidden px-4 py-3 text-[var(--slate)] md:table-cell">
                    {feature.area}
                  </td>
                  <td className="px-4 py-3">
                    <Stamp className={statusStyle[feature.status]}>
                      {statusLabel[feature.status]}
                    </Stamp>
                  </td>
                  <td className="hidden px-4 py-3 font-[family-name:var(--font-mono)] text-[var(--ink)] lg:table-cell">
                    {feature.priority}
                    <span className="ml-2 text-[var(--slate)]/55">effort {feature.effort}</span>
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-sm leading-5 text-[var(--slate)]">{feature.nextStep}</p>
                    <p className="mt-1 font-[family-name:var(--font-mono)] text-[11px] text-[var(--slate)]/55">
                      {feature.templateFit}
                    </p>
                    <button
                      type="button"
                      data-testid="saas-feature-detail-toggle"
                      aria-expanded={expandedId === feature.id}
                      onClick={() => setExpandedId(expandedId === feature.id ? null : feature.id)}
                      className="mt-2 text-xs font-medium text-[var(--teal-deep)] hover:underline"
                    >
                      {expandedId === feature.id ? "Hide details" : "Show details"}
                    </button>
                  </td>
                </tr>
                {expandedId === feature.id && (
                  <tr
                    data-testid="saas-feature-detail"
                    data-id={feature.id}
                    className="border-t border-[var(--line)] bg-[var(--paper)]/55 align-top"
                  >
                    <td colSpan={5} className="px-4 py-4">
                      <div className="grid gap-5 lg:grid-cols-4">
                        {implementationSections.map((section) => (
                          <section key={section.key}>
                            <h3 className="font-[family-name:var(--font-mono)] text-[11px] font-medium uppercase text-[var(--slate)]">
                              {section.label}
                            </h3>
                            <ul className="mt-2 space-y-1.5">
                              {feature.implementation[section.key].map((item) => (
                                <li key={item} className="text-sm leading-5 text-[var(--slate)]/80">
                                  {item}
                                </li>
                              ))}
                            </ul>
                          </section>
                        ))}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
        {visibleFeatures.length === 0 && (
          <p
            data-testid="saas-features-empty"
            className="px-4 py-8 text-center text-sm text-[var(--slate)]/60"
          >
            No features match those filters.
          </p>
        )}
      </div>
    </div>
  );
}
