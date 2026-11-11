// Living reference for the marketing design system (DESIGN.md). Renders the
// real tokens and the real shared/ui/marketing components, so it cannot
// drift from what ships. Registered in development builds only (App.tsx).

import { useState, type CSSProperties, type ReactNode } from "react";

import closingArt from "../../shared/assets/art/closing.webp";
import explodedArt from "../../shared/assets/art/exploded.webp";
import creditsArt from "../../shared/assets/art/feature-credits.webp";
import heroArt from "../../shared/assets/art/hero.webp";
import { BRAND } from "../../shared/lib/brand";
import {
  Art,
  Chip,
  Eyebrow,
  Ledger,
  Marquee,
  MK_BODY,
  MK_DISPLAY,
  MK_H2,
  MK_H3,
  MK_H4,
  MK_INDEX,
  MK_LEAD,
  MK_MONO,
  MK_STATEMENT,
  MK_WRAP,
  MkButton,
  Panel,
  Reveal,
} from "../../shared/ui/marketing";

type Swatch = { token: string; role: string; dark?: boolean };

const COLORS: readonly Swatch[] = [
  { token: "--canvas", role: "Page background" },
  { token: "--sand", role: "Panels and bento cards" },
  { token: "--sand-line", role: "Panel borders" },
  { token: "--lime", role: "The one accent: primary fill, status dot" },
  { token: "--lime-deep", role: "Lime hover" },
  { token: "--carbon", role: "Type, dark bands, footer", dark: true },
  { token: "--carbon-soft", role: "Raised surface on carbon", dark: true },
];

const DERIVED: readonly Swatch[] = [
  { token: "--mk-muted", role: "Secondary text (carbon 60%)", dark: true },
  { token: "--mk-hair", role: "Hairlines (carbon 10%)" },
  { token: "--mk-chip", role: "Chip and soft-button fill (carbon 5%)" },
];

const TYPE: readonly { name: string; spec: string; className: string; sample: string }[] = [
  {
    name: "Display",
    spec: "64 / 1.02 / -0.025em",
    className: MK_DISPLAY,
    sample: "Ship the product.",
  },
  {
    name: "Heading 2",
    spec: "48 / 1.08 / -0.02em",
    className: MK_H2,
    sample: "Everything a SaaS needs",
  },
  {
    name: "Statement",
    spec: "40 / 1.18 / -0.015em",
    className: MK_STATEMENT,
    sample: "A lead in carbon, the rest muted.",
  },
  {
    name: "Heading 3",
    spec: "24 / tight / -0.015em",
    className: MK_H3,
    sample: "Multi-tenant organizations",
  },
  { name: "Heading 4", spec: "20 / -0.01em", className: MK_H4, sample: "Clone and rebrand" },
  {
    name: "Lead",
    spec: "20 / snug / muted",
    className: MK_LEAD,
    sample: "Production-grade from the first commit.",
  },
  {
    name: "Body",
    spec: "16 / relaxed / muted",
    className: MK_BODY,
    sample: "Workspaces with roles, invitations, and org-scoped data.",
  },
  { name: "Index", spec: "12 mono / tabular", className: MK_INDEX, sample: "01" },
];

const LEDGER_FACTS = [
  { label: "Reserve", value: "−12" },
  { label: "Capture", value: "12" },
  { label: "Balance", value: "488" },
] as const;

const TICKER = ["FastAPI", "React", "TypeScript", "Postgres", "Stripe", "Celery", "Valkey"];

// Resolved hex values of the brand tokens on :root. The derived --mk-*
// variables are color-mix() formulas, so their swatches are labelled by role.
function readTokenValues(tokens: readonly string[]): Record<string, string> {
  if (typeof document === "undefined") return {};
  const style = getComputedStyle(document.documentElement);
  return Object.fromEntries(tokens.map((t) => [t, style.getPropertyValue(t).trim()]));
}

function Section({
  index,
  title,
  note,
  children,
}: {
  index: string;
  title: string;
  note: string;
  children: ReactNode;
}) {
  return (
    <section className="border-t border-[var(--mk-hair)] py-16" data-testid="design-system-section">
      <div className={`${MK_WRAP} grid gap-10 lg:grid-cols-[280px_minmax(0,1fr)] lg:gap-16`}>
        <div>
          <p className={MK_INDEX}>{index}</p>
          <h2 className={`mt-3 ${MK_H3}`}>{title}</h2>
          <p className={`mt-3 ${MK_BODY}`}>{note}</p>
        </div>
        <div className="min-w-0">{children}</div>
      </div>
    </section>
  );
}

function SwatchGrid({
  swatches,
  values,
}: {
  swatches: readonly Swatch[];
  values: Record<string, string>;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {swatches.map((s) => (
        <div key={s.token} className="overflow-hidden rounded-xl border border-[var(--sand-line)]">
          <div
            className={`flex h-24 items-end p-3 ${s.dark ? "text-white" : "text-[var(--carbon)]"}`}
            style={{ background: `var(${s.token})` }}
          >
            <span className={`${MK_MONO} text-xs`}>{values[s.token] ?? ""}</span>
          </div>
          <div className="border-t border-[var(--sand-line)] bg-[var(--canvas)] p-3">
            <p className={`${MK_MONO} text-xs text-[var(--carbon)]`}>{s.token}</p>
            <p className="mt-1 text-sm text-[var(--mk-muted)]">{s.role}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function Label({ children }: { children: ReactNode }) {
  return (
    <p className={`${MK_MONO} mb-3 text-[10px] uppercase tracking-[0.08em] text-[var(--mk-muted)]`}>
      {children}
    </p>
  );
}

export default function DesignSystemPage() {
  const [values] = useState(() => readTokenValues(COLORS.map((c) => c.token)));

  return (
    <div className="mk min-h-screen bg-[var(--canvas)]" data-testid="design-system-page">
      <header className={`${MK_WRAP} pb-16 pt-20`}>
        <Eyebrow chip="v1">{BRAND} design system</Eyebrow>
        <h1 className={`mt-5 ${MK_DISPLAY}`}>Carbon &amp; Lime.</h1>
        <p className={`mt-5 max-w-3xl ${MK_LEAD}`}>
          White canvas, carbon type, one lime accent, sand panels, mono facts, and a single series
          of black-block artwork. The rules live in DESIGN.md; everything below is the shipped code.
        </p>
      </header>

      <Section
        index="01"
        title="Color"
        note="Tokens come from shared/brand.toml. Lime is only ever a fill or a dot, always under carbon text."
      >
        <SwatchGrid swatches={COLORS} values={values} />
        <div className="mt-8">
          <Label>Derived inside .mk</Label>
          <SwatchGrid swatches={DERIVED} values={values} />
        </div>
      </Section>

      <Section
        index="02"
        title="Type"
        note="Inter Variable at weight 400 everywhere. Hierarchy is size and tracking, never bold. Facts are IBM Plex Mono."
      >
        <div className="divide-y divide-[var(--mk-hair)] border-y border-[var(--mk-hair)]">
          {TYPE.map((t) => (
            <div
              key={t.name}
              className="grid items-baseline gap-2 py-5 sm:grid-cols-[160px_minmax(0,1fr)]"
            >
              <div>
                <p className="text-sm text-[var(--carbon)]">{t.name}</p>
                <p className={`${MK_MONO} mt-1 text-[11px] text-[var(--mk-muted)]`}>{t.spec}</p>
              </div>
              <p className={`${t.className} truncate`}>{t.sample}</p>
            </div>
          ))}
        </div>
        <div className="mt-8 flex flex-wrap items-center gap-6">
          <Eyebrow>Eyebrow label</Eyebrow>
          <Eyebrow chip="06">Eyebrow with fact</Eyebrow>
          <Eyebrow tone="strong">Strong eyebrow</Eyebrow>
        </div>
      </Section>

      <Section
        index="03"
        title="Buttons"
        note="One lime action per view. Soft is the secondary, ghost is nav-level, outline is for carbon bands."
      >
        <div className="flex flex-wrap items-center gap-3">
          <MkButton size="lg">Get started free</MkButton>
          <MkButton size="lg" variant="soft">
            Read the docs <span aria-hidden>→</span>
          </MkButton>
          <MkButton>Get started</MkButton>
          <MkButton variant="soft">Secondary</MkButton>
          <MkButton variant="ghost">Sign in</MkButton>
        </div>
        <Panel tone="carbon" className="mt-6 flex flex-wrap items-center gap-3 p-6">
          <MkButton size="lg">Create your account</MkButton>
          <MkButton size="lg" variant="outline">
            Talk to us
          </MkButton>
        </Panel>
      </Section>

      <Section
        index="04"
        title="Surfaces"
        note="Panels are flat: 12px radius, 1px border, no shadow. Sand on canvas, canvas on sand, carbon-soft on carbon."
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <Panel className="p-6">
            <Label>Sand</Label>
            <p className={MK_BODY}>Default container for bento cards and showcase panels.</p>
          </Panel>
          <Panel tone="canvas" className="p-6">
            <Label>Canvas</Label>
            <p className={MK_BODY}>Sits on sand, or stands alone with a border.</p>
          </Panel>
          <Panel tone="carbon" className="p-6">
            <p className={`${MK_MONO} mb-3 text-[10px] uppercase tracking-[0.08em] text-white/60`}>
              Carbon
            </p>
            <p className="text-base leading-relaxed text-white/60">
              Raised surface inside a dark band.
            </p>
          </Panel>
        </div>
        <Panel radius="2xl" className="mk-dots mt-4 p-6">
          <Label>Showcase panel · 16px radius · dot grid</Label>
          <div className="flex flex-wrap gap-2">
            {TICKER.map((t) => (
              <Chip key={t}>{t}</Chip>
            ))}
          </div>
        </Panel>
      </Section>

      <Section
        index="05"
        title="Ledger"
        note="The signature data texture. Labels in sans, every value in mono, hairline rows. Use it to show product state, never invented metrics."
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <Ledger label="Credit ledger" facts={LEDGER_FACTS} />
          <Ledger label="Live ledger" facts={LEDGER_FACTS} live />
          <div className="rounded-xl bg-[var(--carbon)] p-4">
            <Ledger label="On carbon" facts={LEDGER_FACTS} tone="dark" live />
          </div>
        </div>
      </Section>

      <Section
        index="06"
        title="Artwork"
        note="One series: matte black modular blocks with exactly one lime element. Light pieces multiply into the surface; dark pieces lighten into carbon."
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Panel className="p-6">
            <Label>Light · on sand</Label>
            <Art src={creditsArt} width={1200} height={800} className="h-56 w-full object-cover" />
          </Panel>
          <div className="rounded-xl border border-[var(--sand-line)] p-6">
            <Label>Light · on canvas</Label>
            <Art
              src={explodedArt}
              width={1024}
              height={1024}
              className="mx-auto h-56 w-auto object-contain"
            />
          </div>
          <Panel radius="2xl" className="relative overflow-hidden p-6 sm:col-span-2">
            <Label>Hero · lime bloom behind the piece</Label>
            <div className="relative mx-auto h-72 max-w-xl">
              <div className="mk-glow absolute left-1/2 top-1/2 h-64 w-64 -translate-x-1/2 -translate-y-1/2" />
              <Art
                src={heroArt}
                width={1536}
                height={864}
                className="relative h-full w-full object-contain"
              />
            </div>
          </Panel>
          <div className="relative h-56 overflow-hidden rounded-xl bg-[var(--carbon)] sm:col-span-2">
            <Art
              src={closingArt}
              width={1536}
              height={656}
              tone="dark"
              className="absolute inset-y-0 right-0 h-full w-auto max-w-none"
            />
            <p
              className={`${MK_MONO} relative p-6 text-[10px] uppercase tracking-[0.08em] text-white/60`}
            >
              Dark · on carbon
            </p>
          </div>
        </div>
      </Section>

      <Section
        index="07"
        title="Motion"
        note="Quiet and purposeful: a slow drift, a pulse on live data, one fade-up per section, a ticker. All of it is off under reduced motion."
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <Panel className="p-6">
            <Label>mk-float</Label>
            <Ledger
              label="Drifting"
              facts={LEDGER_FACTS.slice(0, 2)}
              className="mk-float"
              style={{ "--i": 0 } as CSSProperties}
            />
          </Panel>
          <Panel className="p-6">
            <Label>Reveal</Label>
            <Reveal>
              <p className={MK_BODY}>Fades up once when it enters the viewport.</p>
            </Reveal>
          </Panel>
          <Panel className="p-6">
            <Label>mk-pulse</Label>
            <p className="flex items-center gap-3 text-base text-[var(--carbon)]">
              <span className="mk-pulse h-2 w-2 rounded-full bg-[var(--lime)]" />
              Live status
            </p>
          </Panel>
        </div>
        <div className="mt-4 rounded-xl border border-[var(--sand-line)] py-4">
          <Marquee>
            {[...TICKER, ...TICKER, ...TICKER].map((t, i) => (
              <Chip key={`${t}-${i}`} className="mx-1.5">
                {t}
              </Chip>
            ))}
          </Marquee>
        </div>
      </Section>
    </div>
  );
}
