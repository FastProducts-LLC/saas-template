import { ROUTES } from "../../../shared/lib/routes";

export type SaasFeatureStatus = "included" | "blueprint";

export type SaasFeatureArea =
  "Access" | "Admin" | "Billing" | "Developer" | "Growth" | "Operations" | "Platform" | "Trust";

export type SaasFeaturePriority = "P0" | "P1" | "P2";

export type SaasFeatureEffort = "S" | "M" | "L";

export type SaasFeatureImplementation = {
  database: string[];
  backend: string[];
  frontend: string[];
  verification: string[];
};

export type SaasFeature = {
  id: string;
  title: string;
  area: SaasFeatureArea;
  status: SaasFeatureStatus;
  priority: SaasFeaturePriority;
  effort: SaasFeatureEffort;
  summary: string;
  templateFit: string;
  nextStep: string;
  implementation: SaasFeatureImplementation;
  route?: string;
};

export type SaasBuildPhase = {
  id: string;
  title: string;
  outcome: string;
  featureIds: string[];
};

export const saasBuildPhases: SaasBuildPhase[] = [
  {
    id: "foundation",
    title: "Foundation",
    outcome:
      "Keep the shipped auth, tenant, billing, metering, admin, privacy, and error contracts coherent while product slices are added.",
    featureIds: [
      "auth",
      "organizations",
      "rbac-invitations",
      "billing",
      "metering",
      "admin-console",
      "error-support",
      "privacy-consent",
    ],
  },
  {
    id: "operations",
    title: "Customer operations",
    outcome:
      "Add the workflows teams expect once real customer data, support load, and paid usage show up.",
    featureIds: [
      "notifications",
      "entitlements",
      "support-inbox",
      "data-portability",
      "subscription-billing",
      "social-login",
      "bot-protection",
      "session-management",
      "seo-marketing",
    ],
  },
  {
    id: "developer-platform",
    title: "Developer platform",
    outcome:
      "Expose reliable outbound automation and faster navigation after the core product API stabilizes.",
    featureIds: [
      "api-platform",
      "webhooks",
      "integrations",
      "search",
      "object-storage",
      "observability-metrics",
    ],
  },
  {
    id: "enterprise",
    title: "Enterprise readiness",
    outcome:
      "Layer in procurement and security requirements after the product has repeatable buyer demand.",
    featureIds: ["enterprise-security", "audit-log", "changelog-status", "onboarding", "i18n"],
  },
];

export const saasFeatureCatalog: SaasFeature[] = [
  {
    id: "auth",
    title: "Authentication and account recovery",
    area: "Access",
    status: "included",
    priority: "P0",
    effort: "M",
    summary:
      "Email/password auth, email verification, password reset, refresh tokens, and profile updates.",
    templateFit: "auth domain plus login, register, reset, verify, and profile screens",
    nextStep: "Swap in your identity copy and add OAuth only if the product needs social login.",
    implementation: {
      database: ["users", "refresh_tokens", "email_verified_at", "terms_accepted_at"],
      backend: [
        "auth use cases own registration, login, refresh, password reset, and profile writes",
        "route-level rate limits protect high-risk auth endpoints",
      ],
      frontend: [
        "AuthSplitLayout based login, register, forgot/reset, verify, and profile pages",
        "session provider keeps access tokens in memory and refreshes through the httpOnly cookie",
      ],
      verification: [
        "backend auth tests for token rotation, password reset, and verification",
        "frontend auth component tests plus Playwright signup/login smoke coverage",
      ],
    },
    route: ROUTES.profile,
  },
  {
    id: "organizations",
    title: "Organizations and tenant scoping",
    area: "Platform",
    status: "included",
    priority: "P0",
    effort: "L",
    summary:
      "Shared-schema multi-tenancy with organization scoped records and role-aware route guards.",
    templateFit: "organizations domain, CurrentMember deps, and org switcher",
    nextStep: "Make every new tenant-owned slice carry organization_id and check membership first.",
    implementation: {
      database: [
        "organizations",
        "memberships",
        "organization_id foreign keys on tenant-owned tables",
      ],
      backend: [
        "CurrentMember, CurrentAdmin, and CurrentOwner dependencies resolve access before use cases run",
        "repositories must filter by organization_id for every tenant-scoped query",
      ],
      frontend: [
        "AppLayout org switcher sets the active organization for scoped pages",
        "feature hooks should accept orgId and include it in query keys",
      ],
      verification: [
        "membership tests should assert 404 for non-members and 403 for under-privileged members",
        "new slice tests should include cross-organization access attempts",
      ],
    },
    route: ROUTES.settings,
  },
  {
    id: "rbac-invitations",
    title: "RBAC, invitations, and domain join",
    area: "Access",
    status: "included",
    priority: "P0",
    effort: "M",
    summary:
      "Owner, admin, and member roles with invitations and optional verified-domain auto-join.",
    templateFit: "memberships, invitations, Members page, and company domain setting",
    nextStep: "Add product-specific permissions only when role checks become too coarse.",
    implementation: {
      database: [
        "memberships.role",
        "invitations token_hash/expires_at/accepted_at",
        "organizations.email_domain",
      ],
      backend: [
        "InviteMember, AcceptInvitation, ChangeMemberRole, and RemoveMember enforce role rules",
        "domain-join logic attaches verified users to the claimed organization",
      ],
      frontend: [
        "Members page manages invites, revokes, role changes, and removals",
        "Settings page lets owners claim or release a company domain",
      ],
      verification: [
        "organization tests cover invitation lifecycle and role downgrade edge cases",
        "frontend hooks tests should verify cache invalidation after member writes",
      ],
    },
    route: ROUTES.members,
  },
  {
    id: "billing",
    title: "Billing, checkout, and receipts",
    area: "Billing",
    status: "included",
    priority: "P0",
    effort: "L",
    summary: "Stripe checkout, credit packs, customer portal, and webhook-driven credit grants.",
    templateFit: "billing domain, Billing page, Pricing page, and webhook route",
    nextStep: "Choose whether your product keeps one-time packs or swaps in subscriptions.",
    implementation: {
      database: [
        "billing_accounts maps organizations to Stripe customer ids",
        "credit_transactions stores granted credit movements after checkout",
      ],
      backend: [
        "PaymentGateway port isolates Stripe from billing use cases",
        "checkout.session.completed grants credits idempotently through the credits engine",
      ],
      frontend: [
        "Pricing and Billing pages open checkout or customer portal sessions",
        "invoices and receipts stay behind the provider portal rather than local cache",
      ],
      verification: [
        "billing webhook tests assert duplicate events do not double-grant",
        "frontend billing tests mock checkout session creation and portal errors",
      ],
    },
    route: ROUTES.billing,
  },
  {
    id: "metering",
    title: "Usage metering, quotas, and ledger",
    area: "Billing",
    status: "included",
    priority: "P0",
    effort: "L",
    summary:
      "Reserve, capture, release, and expire credit movements with per-member and API-key attribution.",
    templateFit: "credits domain, wallet hooks, usage tables, and ledger tests",
    nextStep: "Map each paid product action to a stable credit action and cost.",
    implementation: {
      database: [
        "credit_wallets",
        "credit_reservations",
        "credit_transactions",
        "member_credit_limits",
      ],
      backend: [
        "hold_credits handles in-request reserve/capture/release flows",
        "worker-settled jobs reserve in the request and finalize from Celery tasks",
      ],
      frontend: [
        "Billing and dashboard surfaces show balance, allowance, usage, and recent ledger rows",
        "member/API-key attribution should be shown wherever spending is reviewed",
      ],
      verification: [
        "ledger tests should prove wallet balance equals transaction sum",
        "reservation expiry tests should cover dormant org sweeps and failed workers",
      ],
    },
    route: ROUTES.billing,
  },
  {
    id: "api-platform",
    title: "API keys and developer docs",
    area: "Developer",
    status: "included",
    priority: "P1",
    effort: "M",
    summary: "Org-scoped API keys, key revocation, public docs, and LLM-readable API markdown.",
    templateFit: "api_keys domain, API Keys page, product docs page, and public docs/api.md",
    nextStep: "Document new endpoints when each domain slice ships.",
    implementation: {
      database: ["api_keys stores prefix, hash, created_by_id, revoked_at, and last_used_at"],
      backend: [
        "hash raw keys at creation and only return the raw secret once",
        "API-key auth should resolve organization context before metered endpoints run",
      ],
      frontend: [
        "API Keys page handles create, copy-once secret display, key prefix copy, and revoke",
        "Docs page and public docs/api.md should stay aligned with shipped endpoints",
      ],
      verification: [
        "API-key tests should cover revoked keys, wrong org access, and last_used_at updates",
        "docs checks should fail when generated endpoint examples drift",
      ],
    },
    route: ROUTES.apiKeys,
  },
  {
    id: "admin-console",
    title: "Platform admin console",
    area: "Admin",
    status: "included",
    priority: "P0",
    effort: "L",
    summary:
      "Cross-tenant views for users, orgs, customers, credits, invitations, generations, and compliance.",
    templateFit: "admin domain plus /admin route tree",
    nextStep: "Keep operational actions behind superuser checks and audit every sensitive write.",
    implementation: {
      database: [
        "admin_audit_log plus read models over users, organizations, credits, and privacy requests",
      ],
      backend: [
        "admin routes must depend on superuser identity and keep customer-impacting writes narrow",
        "analytics queries should be read-optimized and paginated",
      ],
      frontend: [
        "AdminLayout groups overview, customers, users, orgs, credits, invitations, audit, compliance, and errors",
        "dangerous actions should require explicit confirmation and clear impersonation state",
      ],
      verification: [
        "admin tests should assert ordinary users cannot access every admin endpoint",
        "page tests should cover pagination, filters, and mutation error states",
      ],
    },
    route: ROUTES.admin.overview,
  },
  {
    id: "audit-log",
    title: "Audit log and impersonation controls",
    area: "Trust",
    status: "included",
    priority: "P0",
    effort: "M",
    summary:
      "Admin activity log, customer support impersonation, and visible impersonation exit state.",
    templateFit: "admin_audit_log, AdminAuditPage, and AppLayout impersonation banner",
    nextStep: "Add domain-specific audit events for every new customer-impacting admin action.",
    implementation: {
      database: ["admin_audit_log actor_user_id, action, target_type, target_id, meta, created_at"],
      backend: [
        "write audit entries inside the same use case that performs the sensitive action",
        "impersonation should be explicit, reversible, and visible in every app route",
      ],
      frontend: [
        "AdminAuditPage exposes searchable operational history",
        "AppLayout banner prevents admins from forgetting they are acting as a customer",
      ],
      verification: [
        "mutation tests should assert audit rows are written for admin writes",
        "frontend tests should keep the impersonation banner visible across route changes",
      ],
    },
    route: ROUTES.admin.audit,
  },
  {
    id: "error-support",
    title: "Error correlation and support lookup",
    area: "Operations",
    status: "included",
    priority: "P0",
    effort: "M",
    summary:
      "Problem+json errors, request IDs, global frontend error handling, and admin lookup by reference.",
    templateFit: "shared error catalog, backend error handlers, and AdminErrorLookupPage",
    nextStep: "Add new errors to shared/errors.toml before raising them in a feature slice.",
    implementation: {
      database: [
        "Redis-backed error context store with short TTL",
        "shared/errors.toml as the source of truth",
      ],
      backend: [
        "AppError subclasses render RFC 9457 problem+json with stable internal codes",
        "IdempotencyMiddleware replays completed mutating responses when clients retry",
      ],
      frontend: [
        "shared/api normalizes catalog-aware ApiError objects",
        "global toast, offline, maintenance, form-field, and copy-details surfaces share one error path",
      ],
      verification: [
        "contract tests should fail on backend/frontend catalog drift",
        "client tests should cover validation fields, retry metadata, and copyable references",
      ],
    },
    route: ROUTES.admin.errors,
  },
  {
    id: "privacy-consent",
    title: "Consent, legal pages, and privacy requests",
    area: "Trust",
    status: "included",
    priority: "P0",
    effort: "L",
    summary:
      "Cookie consent, marketing opt-in, terms, privacy policy, and public privacy request intake.",
    templateFit: "consent, legal, emails, and privacy_requests slices",
    nextStep:
      "Tune policy text, retention promises, and privacy request workflow for your jurisdiction.",
    implementation: {
      database: [
        "consent_events",
        "privacy_requests",
        "users.marketing_opt_in",
        "users.email_suppressed",
      ],
      backend: [
        "consent sync records policy version and categories",
        "privacy request workflow tracks intake, verification, fulfillment, rejection, deadlines, and purge",
      ],
      frontend: [
        "CookieConsent gates analytics and stores local preference",
        "Legal pages and PrivacyRequestPage provide public self-service surfaces",
      ],
      verification: [
        "consent tests should assert analytics stays inert until opt-in",
        "privacy request tests should cover SLA fields and payload purge behavior",
      ],
    },
    route: ROUTES.legal.privacyRequest,
  },
  {
    id: "onboarding",
    title: "Onboarding checklist and product tours",
    area: "Growth",
    status: "included",
    priority: "P1",
    effort: "S",
    summary: "Dashboard tour, route-aware hints, and reusable tour storage keys.",
    templateFit: "OnboardingTour, useTour, and dashboard tour definitions",
    nextStep: "Turn product activation milestones into checkable setup steps.",
    implementation: {
      database: [
        "optional future onboarding_events table if server-side activation state is needed",
      ],
      backend: [
        "keep initial tours frontend-only until activation needs reporting or sales visibility",
        "server-side milestones should be append-only events rather than mutable booleans",
      ],
      frontend: [
        "OnboardingTour anchors to data-tour markers and stores completed tours by stable keys",
        "future checklist should link directly to billing, API keys, members, and first product action",
      ],
      verification: [
        "tour tests should cover missing anchors and reduced-motion behavior",
        "activation checklist tests should prove completed steps do not regress after reload",
      ],
    },
    route: ROUTES.dashboard,
  },
  {
    id: "notifications",
    title: "Notifications center",
    area: "Operations",
    status: "blueprint",
    priority: "P1",
    effort: "M",
    summary:
      "In-app notifications for invites, billing events, job completion, low balance, and admin actions.",
    templateFit: "new notifications slice with org-scoped rows and read/unread state",
    nextStep:
      "Create notifications domain, bell menu, notification preferences, and email fanout rules.",
    implementation: {
      database: [
        "notifications(id, organization_id, user_id, type, title, body, link, read_at, created_at)",
        "notification_preferences(user_id, channel, type, enabled)",
      ],
      backend: [
        "NotificationService port emits durable in-app rows and optional email fanout",
        "low-balance, invite, job-finished, privacy-request, and admin-action producers should share one enqueue API",
      ],
      frontend: [
        "sidebar or header bell with unread count, dropdown preview, and full notification list",
        "preferences panel for email/in-app channel choices by notification type",
      ],
      verification: [
        "tests should prove one event creates the intended recipients only",
        "frontend tests should cover mark-read, mark-all-read, empty state, and unread badge updates",
      ],
    },
  },
  {
    id: "webhooks",
    title: "Webhooks and event subscriptions",
    area: "Developer",
    status: "blueprint",
    priority: "P1",
    effort: "L",
    summary:
      "Customer-owned endpoints for delivery of product events with signing, retries, and delivery logs.",
    templateFit: "new webhooks slice using idempotency and request-signing helpers",
    nextStep: "Model endpoint secrets, event types, delivery attempts, and retry backoff.",
    implementation: {
      database: [
        "webhook_endpoints(id, organization_id, url, secret_hash, enabled, event_types)",
        "webhook_deliveries(endpoint_id, event_id, status, attempts, next_attempt_at, response_status)",
      ],
      backend: [
        "sign payloads with timestamped HMAC headers and reject unsupported event types up front",
        "delivery worker should retry transient failures with capped exponential backoff and preserve a delivery log",
      ],
      frontend: [
        "developer settings page for endpoint CRUD, secret rotation, subscribed events, and recent deliveries",
        "copyable signing examples in API docs",
      ],
      verification: [
        "contract tests should validate payload schema and signature generation",
        "worker tests should cover retry, disable, timeout, and permanent failure states",
      ],
    },
  },
  {
    id: "integrations",
    title: "Integration directory",
    area: "Growth",
    status: "blueprint",
    priority: "P2",
    effort: "L",
    summary:
      "OAuth or API-token connections to Slack, Zapier, HubSpot, Google Workspace, or product-specific tools.",
    templateFit: "new integrations slice with encrypted credentials and per-org connection state",
    nextStep: "Start with one integration that directly improves activation or retention.",
    implementation: {
      database: [
        "integration_connections(id, organization_id, provider, status, credentials_ref, scopes, connected_by_id)",
        "integration_events for sync attempts and failures",
      ],
      backend: [
        "provider adapters should hide OAuth refresh, token revocation, and provider-specific rate limits",
        "credentials should be encrypted or stored in a secret manager, never returned to the frontend",
      ],
      frontend: [
        "integration directory with connected/disconnected state, connect flows, disconnect confirmation, and sync health",
        "provider detail pages for scopes, last sync, and troubleshooting",
      ],
      verification: [
        "adapter tests should mock token refresh and provider errors",
        "E2E should cover connect callback, disconnect, and expired-token recovery for the first provider",
      ],
    },
  },
  {
    id: "data-portability",
    title: "Data import, export, and portability",
    area: "Trust",
    status: "blueprint",
    priority: "P1",
    effort: "L",
    summary:
      "CSV import, background export jobs, signed download links, and GDPR portability support.",
    templateFit: "new exports slice plus per-domain serializers",
    nextStep: "Add JSON export first, then CSV imports after validation rules are stable.",
    implementation: {
      database: [
        "export_jobs(id, organization_id, requested_by_id, status, format, download_url, expires_at)",
        "import_jobs with source filename, validation summary, and row error counts",
      ],
      backend: [
        "domain serializers should own their own portable JSON shape",
        "exports should run in Celery and write short-lived artifacts outside the request transaction",
      ],
      frontend: [
        "exports page with request button, status polling, download links, and expiry copy",
        "imports should provide preview, validation errors, and all-or-nothing submit controls",
      ],
      verification: [
        "tests should assert exported data is tenant-scoped and excludes secrets",
        "import tests should cover invalid rows, duplicate handling, rollback, and large-file limits",
      ],
    },
  },
  {
    id: "search",
    title: "Global search and command palette",
    area: "Platform",
    status: "blueprint",
    priority: "P2",
    effort: "M",
    summary:
      "Fast navigation and tenant-scoped search across records, members, docs, settings, and support IDs.",
    templateFit: "frontend command palette plus backend search endpoint per searchable slice",
    nextStep: "Index only records the current membership can access and log search failures.",
    implementation: {
      database: [
        "search can start with database queries, then graduate to search_documents if ranking needs improve",
        "search audit rows are useful only for support and abuse investigations",
      ],
      backend: [
        "GET /orgs/{org_id}/search should fan out to slice-owned query providers with strict membership checks",
        "results should return type, title, subtitle, route, and highlighted matched fields",
      ],
      frontend: [
        "command palette opened from keyboard and nav search",
        "group results by type and include recent routes when query is empty",
      ],
      verification: [
        "tests should prove results never leak cross-org records",
        "frontend tests should cover keyboard navigation, no-results, and route selection",
      ],
    },
  },
  {
    id: "entitlements",
    title: "Feature flags, plan gates, and entitlements",
    area: "Platform",
    status: "blueprint",
    priority: "P1",
    effort: "M",
    summary:
      "Controlled rollout, plan limits, beta access, and kill switches for expensive workflows.",
    templateFit: "new entitlements slice consumed by frontend nav, routes, and backend use cases",
    nextStep: "Separate deploy-time flags from customer entitlements and billable plan gates.",
    implementation: {
      database: [
        "feature_flags(key, enabled, rollout_rules)",
        "organization_entitlements(organization_id, key, limit_value, source, expires_at)",
      ],
      backend: [
        "EntitlementService should answer allowed/limit decisions for use cases before expensive work starts",
        "plan gates must be enforced on the backend even when the UI hides controls",
      ],
      frontend: [
        "nav items, empty states, and upgrade prompts consume entitlement snapshots",
        "admin/customer pages expose overrides with an audit trail",
      ],
      verification: [
        "tests should cover denied access, limit exhaustion, overrides, and expired entitlements",
        "frontend tests should assert gated controls cannot trigger mutations",
      ],
    },
  },
  {
    id: "support-inbox",
    title: "Customer support inbox and help center",
    area: "Operations",
    status: "blueprint",
    priority: "P1",
    effort: "M",
    summary:
      "Ticket intake, support articles, account context, and links to request IDs or admin actions.",
    templateFit: "new support slice backed by error references and admin customer profiles",
    nextStep: "Start with authenticated ticket creation plus an admin queue.",
    implementation: {
      database: [
        "support_tickets(id, organization_id, requester_id, subject, status, priority, last_message_at)",
        "support_messages(ticket_id, author_user_id, body, attachments, created_at)",
      ],
      backend: [
        "ticket creation should attach org, user, browser context, optional error reference, and billing/customer summary",
        "admin replies should optionally send transactional email and update last_message_at",
      ],
      frontend: [
        "customer support inbox with ticket list, create form, message thread, and status badges",
        "admin queue with owner, priority, customer context, and links to error lookup",
      ],
      verification: [
        "tests should assert users only see tickets for their organizations",
        "message tests should cover attachments, admin-only notes, and email failure tolerance",
      ],
    },
  },
  {
    id: "changelog-status",
    title: "Changelog, announcements, and status page",
    area: "Operations",
    status: "blueprint",
    priority: "P2",
    effort: "S",
    summary:
      "Public release notes, in-app announcements, incident status, and maintenance notices.",
    templateFit: "static public pages first, then admin-managed announcements",
    nextStep: "Add a lightweight changelog route and reuse email/web notification channels later.",
    implementation: {
      database: [
        "announcements(id, audience, title, body, starts_at, ends_at)",
        "status_incidents(id, status, impact, started_at, resolved_at) if status moves in-app",
      ],
      backend: [
        "start with static markdown release notes, then add admin-managed announcements when cadence justifies it",
        "maintenance banners should be cacheable but quickly dismissible",
      ],
      frontend: [
        "public changelog route, authenticated announcement banner, and optional status page link",
        "dismissal state should be per user and announcement id",
      ],
      verification: [
        "tests should cover scheduled visibility windows and audience targeting",
        "frontend tests should verify dismissal persists without hiding future announcements",
      ],
    },
  },
  {
    id: "enterprise-security",
    title: "Enterprise security: MFA, SSO, and SCIM",
    area: "Trust",
    status: "blueprint",
    priority: "P1",
    effort: "L",
    summary:
      "TOTP or WebAuthn MFA, organization SAML/OIDC login, and optional directory provisioning.",
    templateFit: "extend auth and organizations with org-level identity provider settings",
    nextStep: "Ship MFA for superusers first, then SSO/SCIM when enterprise deals require it.",
    implementation: {
      database: [
        "mfa_factors(user_id, type, secret_ref, confirmed_at, last_used_at)",
        "identity_providers(organization_id, protocol, metadata, enforced_at)",
        "scim_tokens and external user ids if provisioning ships",
      ],
      backend: [
        "login becomes password-valid then challenge-required until MFA is satisfied",
        "SSO should map verified IdP assertions to org membership without bypassing suspended-user checks",
      ],
      frontend: [
        "profile MFA enrollment, recovery-code display, login challenge screens, and org SSO settings",
        "enterprise settings should explain enforcement before owners turn it on",
      ],
      verification: [
        "auth tests should cover enrollment, challenge, recovery, lost-factor admin reset, and remember-device policy",
        "SSO tests should cover assertion validation, wrong audience, disabled IdP, and deprovisioning",
      ],
    },
  },
  {
    id: "subscription-billing",
    title: "Subscription plans and revenue reporting",
    area: "Billing",
    status: "blueprint",
    priority: "P1",
    effort: "L",
    summary:
      "Recurring Stripe plans with trials, proration, dunning, cancel/win-back flows, and founder revenue metrics.",
    templateFit:
      "extend the billing PaymentGateway port and webhook route with subscription lifecycle events",
    nextStep:
      "Decide pack-versus-plan pricing, then map subscription status to entitlements and allowances.",
    implementation: {
      database: [
        "subscriptions(id, organization_id, stripe_subscription_id, plan_key, status, current_period_end, cancel_at_period_end)",
        "processed webhook event ids stored so grants and downgrades stay idempotent",
      ],
      backend: [
        "handle customer.subscription.created/updated/deleted and invoice.payment_failed idempotently and out of order",
        "subscription status should drive plan entitlements and monthly credit allowances",
      ],
      frontend: [
        "plan cards on Pricing with subscription-mode checkout plus a manage-plan billing surface",
        "cancel flow with retention offer, reactivation for lapsed orgs, and an admin MRR/churn view",
      ],
      verification: [
        "webhook tests should cover duplicate events, failed payments, and downgrade timing",
        "revenue reporting should reconcile MRR against Stripe as the source of truth",
      ],
    },
  },
  {
    id: "social-login",
    title: "Social login (OAuth sign-in)",
    area: "Access",
    status: "blueprint",
    priority: "P2",
    effort: "M",
    summary:
      "Sign in with Google and other OAuth providers, linked safely to existing email accounts.",
    templateFit: "extend the auth domain with an oauth_identities table and provider adapters",
    nextStep: "Add Google first; link by verified email and keep password login as the fallback.",
    implementation: {
      database: [
        "oauth_identities(user_id, provider, provider_subject, email, created_at) unique on provider+subject",
      ],
      backend: [
        "authorization-code flow with PKCE verified server-side, issuing the same session tokens as password login",
        "account linking must require a verified email match or an explicit signed-in link step",
      ],
      frontend: [
        "provider buttons on login/register plus a connected-accounts section on the profile page",
        "callback errors and account-exists conflicts surface through catalog error codes",
      ],
      verification: [
        "tests should cover new-user signup, existing-email linking, and unverified-email rejection",
        "E2E should exercise the callback roundtrip against a mocked provider",
      ],
    },
  },
  {
    id: "object-storage",
    title: "Object storage and file uploads",
    area: "Platform",
    status: "blueprint",
    priority: "P1",
    effort: "M",
    summary:
      "S3/Spaces-backed file storage behind a port with presigned upload/download URLs, replacing the local media volume.",
    templateFit: "new core FileStorage port adopted by generations and future upload features",
    nextStep:
      "Introduce a FileStorage protocol, then move generation assets to Spaces with presigned GETs.",
    implementation: {
      database: [
        "stored_files(id, organization_id, key, content_type, size_bytes, created_by_id, expires_at)",
      ],
      backend: [
        "FileStorage port with a local-disk dev adapter and an S3/Spaces production adapter",
        "downloads should use short-lived presigned URLs instead of streaming through the API",
      ],
      frontend: [
        "uploads go direct-to-storage with presigned PUTs and progress state",
        "asset views should tolerate URL expiry by refetching a fresh link",
      ],
      verification: [
        "storage tests should assert tenant-scoped keys and denied cross-org reads",
        "lifecycle tests should cover orphan cleanup for failed and expired assets",
      ],
    },
  },
  {
    id: "session-management",
    title: "Active sessions and device management",
    area: "Access",
    status: "blueprint",
    priority: "P1",
    effort: "S",
    summary:
      "Per-user list of active sessions with device metadata, per-session revoke, and sign-out-everywhere.",
    templateFit: "extend auth refresh_tokens with device metadata and a profile Sessions panel",
    nextStep:
      "Record user agent and IP at refresh-token creation, then expose list and revoke endpoints.",
    implementation: {
      database: [
        "refresh_tokens gains user_agent, ip_address, last_used_at, and a stable session family id",
      ],
      backend: [
        "GET /auth/sessions lists the current user's active refresh-token families",
        "revoking a session invalidates its refresh chain without touching other devices",
      ],
      frontend: [
        "profile Sessions panel with current-device marker, last-active time, and revoke buttons",
        "sign-out-everywhere action that states whether the current session survives",
      ],
      verification: [
        "tests should prove a revoked session cannot refresh while others still can",
        "rotation tests should keep session identity stable across token rotation",
      ],
    },
  },
  {
    id: "bot-protection",
    title: "Bot protection and abuse prevention",
    area: "Access",
    status: "blueprint",
    priority: "P1",
    effort: "S",
    summary:
      "CAPTCHA/Turnstile challenges on signup and password reset layered on the existing rate limits.",
    templateFit: "CaptchaVerifier port checked ahead of high-risk auth use cases",
    nextStep:
      "Add Cloudflare Turnstile verification to register and reset endpoints behind a config flag.",
    implementation: {
      database: ["no new tables; an optional signup_challenges log helps abuse investigations"],
      backend: [
        "CaptchaVerifier port called before high-risk auth use cases run, no-op in dev and test",
        "challenge verification composes with existing rate limits and email-validation screening",
      ],
      frontend: [
        "Turnstile widget on register, forgot-password, and repeated failed logins",
        "graceful degradation copy when the challenge script fails to load",
      ],
      verification: [
        "tests should cover missing, invalid, and replayed challenge tokens",
        "dev-mode bypass must keep signup smoke tests deterministic",
      ],
    },
  },
  {
    id: "i18n",
    title: "Internationalization and localization",
    area: "Platform",
    status: "blueprint",
    priority: "P2",
    effort: "L",
    summary:
      "Locale framework for UI strings, dates, numbers, emails, and error copy with a per-user language preference.",
    templateFit: "frontend message catalogs plus locale-aware email templates and error copy",
    nextStep:
      "Extract UI strings into a message catalog first; translate error and email copy last.",
    implementation: {
      database: ["users.locale preference column with a sensible default"],
      backend: [
        "Accept-Language and users.locale select email template and error copy variants",
        "shared/errors.toml UX copy needs a per-locale layer generated into both catalogs",
      ],
      frontend: [
        "message-catalog framework with typed keys and ICU plurals",
        "locale switcher plus Intl-based date, number, and currency formatting",
      ],
      verification: [
        "CI should fail on missing or unused translation keys",
        "key screens should render in a pseudo-locale to catch hardcoded strings",
      ],
    },
  },
  {
    id: "seo-marketing",
    title: "SEO plumbing and marketing content",
    area: "Growth",
    status: "blueprint",
    priority: "P2",
    effort: "S",
    summary:
      "sitemap.xml, robots.txt, per-route meta and OpenGraph tags, and a lightweight blog/content surface.",
    templateFit: "frontend public assets plus prerendered marketing routes",
    nextStep: "Ship robots.txt, sitemap.xml, and canonical/OG tags before investing in a blog.",
    implementation: {
      database: ["optional blog_posts table only if content outgrows markdown files"],
      backend: [
        "serve sitemap.xml and robots.txt with correct cache headers",
        "public marketing routes should be prerendered so crawlers see real content",
      ],
      frontend: [
        "route-level title, meta, OpenGraph, and canonical URL management",
        "markdown-backed blog or announcements reader on the public site",
      ],
      verification: [
        "checks should confirm sitemap URLs return 200 and match public routes",
        "Lighthouse SEO scores should gate regressions before release",
      ],
    },
  },
  {
    id: "observability-metrics",
    title: "Metrics, tracing, and alerting",
    area: "Operations",
    status: "blueprint",
    priority: "P1",
    effort: "M",
    summary:
      "OpenTelemetry metrics and traces plus uptime checks and alert rules, layered on Sentry and structured logs.",
    templateFit:
      "extend core observability with OpenTelemetry instrumentation and health-based alerts",
    nextStep:
      "Instrument FastAPI and Celery with OpenTelemetry, then alert on error rate and queue depth.",
    implementation: {
      database: ["no app tables; metrics and traces live in the telemetry backend"],
      backend: [
        "traces across API, database, and Celery correlated with X-Request-ID",
        "export per-route RED metrics and per-queue depth and latency",
      ],
      frontend: [
        "web-vitals reporting wired through the consent-gated analytics path",
        "admin overview tiles for error rate and job lag once metrics exist",
      ],
      verification: [
        "alert rules should fire on health-gate failures, error-rate spikes, and dead queues",
        "a smoke trace should link an API request to its resulting Celery span",
      ],
    },
  },
];

export function countSaasFeatures(status?: SaasFeatureStatus): number {
  if (!status) return saasFeatureCatalog.length;
  return saasFeatureCatalog.filter((feature) => feature.status === status).length;
}
