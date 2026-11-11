// Marketing content: rewrite the product story here on a rebrand (see docs/customization.md).
// Shared content may import only from shared/lib, never from features.

import { BRAND } from "../lib/brand";
import { API_KEY_PREFIX } from "../lib/policy";

// A labelled fact rendered in mono inside the home page's mini ledgers.
export type Fact = { readonly label: string; readonly value: string };
export type Feature = {
  readonly title: string;
  readonly body: string;
  readonly ledger: string;
  readonly facts: readonly Fact[];
};
export type Step = { readonly title: string; readonly body: string };
export type Faq = { readonly q: string; readonly a: string };
export type AccessRow = { readonly label: string; readonly value: string };
export type EnginePhase = { readonly title: string; readonly body: string; readonly fact: Fact };
export type LedgerCard = { readonly label: string; readonly facts: readonly Fact[] };

type Section = { readonly eyebrow: string; readonly heading: string };
type CtaLabels = { readonly signedInLabel: string; readonly signedOutLabel: string };

export type HomeContent = {
  readonly hero: CtaLabels & {
    readonly eyebrow: string;
    readonly headline: string;
    readonly description: string;
    readonly docsLabel: string;
  };
  // Illustrative product vignette under the hero: four mini ledgers floating
  // around the hero artwork.
  readonly heroPanel: {
    readonly cards: readonly [LedgerCard, LedgerCard, LedgerCard, LedgerCard];
  };
  readonly stack: { readonly label: string; readonly items: readonly string[] };
  // Two-tone statement: `lead` renders in full ink, `rest` continues muted.
  readonly statement: { readonly lead: string; readonly rest: string };
  readonly featuresSection: Section;
  // Dark spotlight band on the credit engine; phases map left-to-right onto
  // the three pedestals in the band's artwork.
  readonly engine: {
    readonly eyebrow: string;
    readonly lead: string;
    readonly rest: string;
    readonly phases: readonly [EnginePhase, EnginePhase, EnginePhase];
  };
  readonly stepsSection: Section;
  readonly faqSection: { readonly heading: string; readonly description: string };
  readonly closing: CtaLabels & { readonly heading: string; readonly description: string };
  readonly features: readonly Feature[];
  readonly steps: readonly Step[];
  readonly faqs: readonly Faq[];
};

// Replace this copy with your product's story on a rebrand.
export const HOME_CONTENT = {
  hero: {
    eyebrow: "Production modules in the box",
    headline: "Ship the product. Skip the plumbing.",
    description:
      "Auth, organizations, billing, and metered AI — production-grade from the first commit.",
    docsLabel: "Read the API docs",
    signedInLabel: "Go to dashboard",
    signedOutLabel: "Get started free",
  },
  heroPanel: {
    cards: [
      {
        label: "Reserving credits",
        facts: [
          { label: "Hold", value: "−12" },
          { label: "Capture", value: "12" },
          { label: "Release", value: "0" },
        ],
      },
      {
        label: "Checking role",
        facts: [
          { label: "Owner", value: "Allowed" },
          { label: "Admin", value: "Allowed" },
          { label: "Member", value: "Read only" },
        ],
      },
      {
        label: "Issuing API key",
        facts: [
          { label: "Key", value: `${API_KEY_PREFIX}····4f2a` },
          { label: "Scope", value: "Organization" },
        ],
      },
      {
        label: "Settling generation",
        facts: [
          { label: "Image", value: "Delivered" },
          { label: "Video", value: "Running" },
          { label: "LLM", value: "Delivered" },
        ],
      },
    ],
  },
  stack: {
    label: "Built with",
    items: ["FastAPI", "React", "TypeScript", "Postgres", "Stripe", "Celery", "Valkey"],
  },
  statement: {
    lead: "A production-grade starting point for your next product.",
    rest: "Organizations with roles and invitations, Stripe credit packs, a hold/capture credit engine, working AI endpoints, API keys, and a full admin console.",
  },
  featuresSection: {
    eyebrow: "What ships in the box",
    heading: "Everything a SaaS needs before the product",
  },
  engine: {
    eyebrow: "The credit engine",
    lead: "Customers are never charged for errors.",
    rest: "Every metered action runs on a two-phase ledger, in the request or across a background job.",
    phases: [
      {
        title: "Reserve",
        body: "A hold is placed on the organization's wallet before the provider call starts.",
        fact: { label: "Hold", value: "−12" },
      },
      {
        title: "Capture",
        body: "The hold is captured only when a result is actually delivered.",
        fact: { label: "Captured", value: "12" },
      },
      {
        title: "Release",
        body: "On failure the hold is released and the credits return to the wallet.",
        fact: { label: "Returned", value: "12" },
      },
    ],
  },
  stepsSection: {
    eyebrow: "How it works",
    heading: "From template to your product",
  },
  faqSection: {
    heading: "Frequently asked questions",
    description: "The short version of what you get and how it is put together.",
  },
  closing: {
    heading: `Start building on ${BRAND}`,
    description:
      "Create a workspace, invite your team, and make your first metered API call in minutes.",
    signedInLabel: "Go to dashboard",
    signedOutLabel: "Create your account",
  },
  features: [
    {
      title: "Multi-tenant organizations",
      body: "Workspaces with owner/admin/member roles, invitations, email-domain auto-join, and org-scoped data everywhere.",
      ledger: "Members",
      facts: [
        { label: "Dev User", value: "Owner" },
        { label: "Ada Lovelace", value: "Admin" },
        { label: "Grace Hopper", value: "Member" },
      ],
    },
    {
      title: "Stripe billing + credit engine",
      body: "One-time credit packs via Stripe Checkout, a hold/capture/release ledger for metered actions, and per-member monthly caps.",
      ledger: "Credit ledger",
      facts: [
        { label: "Reserve", value: "−12" },
        { label: "Capture", value: "12" },
        { label: "Balance", value: "488" },
      ],
    },
    {
      title: "Metered AI actions",
      body: "Working image, video, and LLM endpoints on the two-phase credit flow: reserve in the request, settle from the worker.",
      ledger: "Generations",
      facts: [
        { label: "Image", value: "Delivered" },
        { label: "Video", value: "Running" },
        { label: "LLM", value: "Delivered" },
      ],
    },
    {
      title: "API keys",
      body: `Org-scoped ${API_KEY_PREFIX} keys that unlock the same member endpoints programmatically, with usage attributed to the key.`,
      ledger: "Key",
      facts: [
        { label: "Token", value: `${API_KEY_PREFIX}····4f2a` },
        { label: "Scope", value: "Organization" },
        { label: "Usage", value: "Attributed" },
      ],
    },
    {
      title: "Admin console",
      body: "Superuser back office: customers, credit wallets, generations, invitations, audit log, error lookup, and privacy queue.",
      ledger: "Back office",
      facts: [
        { label: "Customers", value: "Wallets" },
        { label: "Audit log", value: "Every action" },
        { label: "Errors", value: "By request ID" },
      ],
    },
    {
      title: "GDPR toolkit",
      body: "Consent-gated analytics, cookie banner with audit trail, DSAR intake + admin queue, and retention purge jobs.",
      ledger: "Privacy",
      facts: [
        { label: "Analytics", value: "Consent-gated" },
        { label: "Cookie banner", value: "Audit trail" },
        { label: "DSAR intake", value: "Admin queue" },
        { label: "Retention", value: "Purge jobs" },
      ],
    },
  ],
  steps: [
    {
      title: "Clone and rebrand",
      body: "Set the app name, theme tokens, and legal placeholders — docs/customization.md walks through every touchpoint.",
    },
    {
      title: "Add your product slice",
      body: "One vertical slice per feature: pure domain, use cases behind ports, imperative-mapped ORM, thin router. Mirror it in the frontend.",
    },
    {
      title: "Meter it with credits",
      body: "Reserve before the provider call, capture on a delivered result, release on failure — the generations and LLM slices show both flows.",
    },
    {
      title: "Ship it",
      body: "Docker Compose dev stack, zero-downtime rolling deploy, GHCR CI, and a shared-Caddy production overlay are already wired.",
    },
  ],
  faqs: [
    {
      q: "What's in the stack?",
      a: "FastAPI + SQLAlchemy (imperative mapping) + Alembic + Celery on the backend; React, TypeScript, Vite, and TanStack Query on the frontend; Postgres, Valkey, and Mailpit in the dev compose stack.",
    },
    {
      q: "How is the code organized?",
      a: "DDD vertical slices: each feature owns its domain, application, infrastructure, and interface layers, with dependencies pointing inward only. The frontend mirrors the same slices.",
    },
    {
      q: "What does the credit engine do?",
      a: "It meters any action you point at it. Holds are placed before work starts, captured when a result is delivered, and released on failure — so customers are never charged for errors.",
    },
    {
      q: "Is this production-ready?",
      a: "It ships with an error catalog with RFC 9457 responses, idempotent mutations, rate limits, tenancy guards, consent-gated analytics, and a documented deploy pipeline. Swap in your branding and product logic, then launch.",
    },
  ],
} as const satisfies HomeContent;

export type AuthPanelContent = {
  readonly entryLabel: string;
  readonly eyebrow: string;
  readonly headline: string;
  readonly blurb: string;
  readonly accessHeading: string;
  readonly status: string;
  readonly accessRows: readonly AccessRow[];
  readonly capabilities: readonly string[];
};

export const AUTH_PANEL_CONTENT = {
  entryLabel: "APP ENTRY",
  eyebrow: "AUTH / WORKSPACE",
  headline: "Secure access for operational teams",
  blurb: "Sign in once to reach workspaces, billing, API keys, and audit-ready account settings.",
  accessHeading: "Access posture",
  status: "READY",
  accessRows: [
    { label: "Session scope", value: "Org-bound" },
    { label: "Login surface", value: "Rate limited" },
    { label: "Recovery flow", value: "Available" },
  ],
  capabilities: ["Workspace", "Billing", "API keys"],
} as const satisfies AuthPanelContent;

// Organization plan copy; prices and allowances come from the public catalog.
export const PLAN_CONTENT = {
  heading: "Plans for your organization",
  description: "Choose a plan with monthly credits, then top up whenever you need more.",
  signedOut: "Start free",
  signedIn: "Choose plan",
  /** Plan highlighted as the suggested choice in plan pickers. */
  recommended: "pro",
  taglines: {
    free: "For trying things out.",
    pro: "For individuals doing regular work.",
    team: "For teams sharing one balance.",
  },
  features: {
    free: ["Start with a monthly credit allowance", "Add credit top-ups when needed"],
    pro: ["More monthly credits for regular work", "Shared organization credit balance"],
    team: ["A larger monthly allowance for your team", "Shared organization credit balance"],
  },
} as const;
