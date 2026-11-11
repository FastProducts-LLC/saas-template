// Soft compliance inventory for platform admins.
// Status reflects what the product ships today — not a live scanner or legal opinion.
// Update this list when you ship or retire a control.

export type ComplianceStatus = "in_place" | "partial" | "missing";

export type ComplianceItem = {
  id: string;
  title: string;
  status: ComplianceStatus;
  framework: string;
  summary: string;
  /** Where it lives today, or what to build next. */
  software: string;
};

export type ComplianceCategory = {
  id: string;
  title: string;
  blurb: string;
  items: ComplianceItem[];
};

export const complianceCategories: ComplianceCategory[] = [
  {
    id: "privacy-rights",
    title: "Privacy rights (GDPR / CCPA)",
    blurb: "Data-subject rights the privacy policy promises, and whether software backs them.",
    items: [
      {
        id: "marketing-consent",
        title: "Marketing email consent",
        status: "in_place",
        framework: "GDPR consent",
        summary:
          "Opt-in at signup and on profile; list sync only when marketing_opt_in is true; unsubscribe webhook flips consent off.",
        software: "auth + emails domains (marketing_opt_in, Resend/list webhooks)",
      },
      {
        id: "legal-pages",
        title: "Published Privacy Policy & Terms",
        status: "in_place",
        framework: "Transparency",
        summary: "Public /privacy and /terms pages with CCPA and GDPR sections.",
        software: "frontend/src/features/legal",
      },
      {
        id: "dsar-access-export",
        title: "Self-service data access / portability",
        status: "missing",
        framework: "GDPR Art. 15/20 · CCPA right to know",
        summary:
          "Policy offers access/portability via email; there is no in-app export of account, membership, billing, or activity data.",
        software: "Build: DSAR export job + download endpoint (JSON/ZIP) and admin intake queue",
      },
      {
        id: "dsar-erasure",
        title: "Account / personal-data erasure",
        status: "partial",
        framework: "GDPR Art. 17 · CCPA delete",
        summary:
          "Admins can deactivate users and revoke sessions; marketing contact can be deleted. No end-user delete-account flow or cascading PII purge across orgs, credits, generations, and audit rows.",
        software:
          "Build: DeleteAccount use case + retention exceptions + marketing erasure orchestration",
      },
      {
        id: "dsar-queue",
        title: "Privacy request intake & SLA tracking",
        status: "partial",
        framework: "GDPR / CCPA process",
        summary:
          "Public /privacy/request intake plus admin queue with verify → fulfill/forward → close, 45-day deadline field. Identity verification is still ops-manual (no automated ID proofing).",
        software: "privacy_requests domain + AdminPrivacyRequestsPage + /privacy/request",
      },
      {
        id: "cookie-consent",
        title: "Cookie / analytics consent banner",
        status: "in_place",
        framework: "ePrivacy / GDPR",
        summary:
          "Granular opt-in banner (Essential always-on, Analytics default-off) gates GA4: reject or no choice loads nothing; query strings and resource ids stripped, IP anonymization on. Versioned choice in localStorage, re-openable via footer/profile Cookie settings; signed-in decisions append to a backend audit trail (consent_events). Fonts self-hosted. Policy §4/§5 updated.",
        software:
          "features/consent (banner + store + /api/consent sync) + shared/lib/analytics.ts + domains/consents; VITE_GA_MEASUREMENT_ID build arg (unset ⇒ GA inert)",
      },
      {
        id: "first-party-analytics",
        title: "First-party product analytics with account opt-out",
        status: "in_place",
        framework: "GDPR Art. 6(1)(f) / Art. 21",
        summary:
          "Feature-usage events for signed-in accounts go to our own activity_events table (legitimate interest; nothing stored on the device, so not banner-gated; no anonymous rows). Profile → Privacy toggle sets users.analytics_opt_out, which stops client AND server events for the account and disables GA for it. Properties are identifiers/enums/numbers only (sanitized server-side). Rows purge after 24 months and cascade on account deletion. Policy §2(b)/§4/§8/§12/§14 updated. Have counsel confirm the legitimate-interest position for your market.",
        software:
          "domains/analytics (POST /api/events, CaptureServerEvent, daily purge) + shared/lib/track.ts + shared/events.toml registry (scripts/gen_events.py)",
      },
    ],
  },
  {
    id: "security-access",
    title: "Security & access control",
    blurb: "Authn/authz and operational security already in the stack.",
    items: [
      {
        id: "password-hashing",
        title: "Password hashing (Argon2)",
        status: "in_place",
        framework: "Security",
        summary: "Passwords stored via Argon2 hasher; never plaintext.",
        software: "auth infrastructure/security.py",
      },
      {
        id: "sessions",
        title: "Session revoke & sign-out everywhere",
        status: "in_place",
        framework: "Security",
        summary:
          "Refresh tokens revoked on password change/reset; admin can force sign-out everywhere; nightly purge of expired tokens.",
        software: "auth use cases + purge_refresh_tokens beat task",
      },
      {
        id: "email-verification-gate",
        title: "Email verification policy",
        status: "in_place",
        framework: "Security",
        summary:
          "EMAIL_VERIFICATION_GATE=sensitive (default) gates org create, billing, API keys, and AI via CurrentVerifiedUser; DOMAIN_CLAIM_MODE=verified_claim blocks domain squat before mailbox proof. Flip both in env per project.",
        software: "config.py + auth/organizations deps (docs/customization.md § Security)",
      },
      {
        id: "rate-limits",
        title: "Auth & AI rate limits",
        status: "in_place",
        framework: "Abuse prevention",
        summary: "IP rate limits on register/login/reset and generation/LLM routes.",
        software: "app.core.ratelimit + route decorators",
      },
      {
        id: "tenancy-rbac",
        title: "Org tenancy & role gates",
        status: "in_place",
        framework: "Access control",
        summary:
          "Tenant-scoped tables and CurrentMember/Admin/Owner deps on /orgs/{org_id}/… routes.",
        software: "organizations interface/deps + repository filters",
      },
      {
        id: "admin-audit",
        title: "Platform admin audit log",
        status: "in_place",
        framework: "Accountability",
        summary:
          "Append-only admin_audit_log for deactivate, impersonate, suspend, credit adjust, etc. Visible at /admin/audit.",
        software: "admin domain + AdminAuditPage",
      },
      {
        id: "error-correlation",
        title: "Error correlation & support lookup",
        status: "in_place",
        framework: "Ops / security",
        summary:
          "RFC 9457 problem+json with X-Request-ID; 7-day Redis context resolvable in Error lookup.",
        software: "app.core.error_handling + AdminErrorLookupPage",
      },
      {
        id: "idempotency",
        title: "Idempotent mutating requests",
        status: "in_place",
        framework: "Integrity",
        summary: "Idempotency-Key middleware on mutating API calls; credit grants deduped.",
        software: "IdempotencyMiddleware + credits ledger keys",
      },
      {
        id: "mfa",
        title: "Multi-factor authentication (MFA)",
        status: "missing",
        framework: "Security",
        summary: "Email/password only. No TOTP/WebAuthn for users or superusers.",
        software: "Build: MFA enrollment + challenge on login (priority for superusers)",
      },
      {
        id: "sso",
        title: "Enterprise SSO (SAML/OIDC)",
        status: "missing",
        framework: "Enterprise security",
        summary: "No org-level IdP login or SCIM provisioning.",
        software: "Build when enterprise requires it: SSO + optional SCIM",
      },
    ],
  },
  {
    id: "retention-ops",
    title: "Retention, backups & incident readiness",
    blurb: "What we keep, how long, and whether recovery/incident software exists.",
    items: [
      {
        id: "db-backups",
        title: "Managed Postgres backups + PITR",
        status: "in_place",
        framework: "Availability",
        summary: "Documented DO managed DB daily backups and point-in-time recovery.",
        software: "docs/backups.md (ops — not app code)",
      },
      {
        id: "error-ttl",
        title: "Short-lived error context retention",
        status: "in_place",
        framework: "Minimization",
        summary: "Detailed request error context expires after ~7 days in Redis.",
        software: "error context store TTL",
      },
      {
        id: "retention-jobs",
        title: "Automated data retention / purge policies",
        status: "partial",
        framework: "GDPR storage limitation",
        summary:
          "Refresh tokens purged nightly; privacy-request raw payloads cleared after 90 days (audit metadata kept). Still no sweeps for generations, admin audit, or inactive accounts.",
        software: "auth + privacy_requests Celery beat tasks; extend per remaining data class",
      },
      {
        id: "breach-playbook",
        title: "Breach notification workflow",
        status: "missing",
        framework: "GDPR Art. 33/34 · state laws",
        summary:
          "Policy promises legally required notice; no in-product incident log, affected-user export, or notification templates.",
        software:
          "Build: incident record + affected-tenant query + email templates (plus legal runbook)",
      },
      {
        id: "policy-acceptance",
        title: "Terms / Privacy version acceptance log",
        status: "missing",
        framework: "Evidence",
        summary:
          "Users agree at signup via link, but we do not store which policy version was accepted or when.",
        software:
          "Build: policy_version + accepted_at on user (and re-consent on material changes)",
      },
    ],
  },
];

export function countByStatus(categories: ComplianceCategory[] = complianceCategories) {
  const counts = { in_place: 0, partial: 0, missing: 0, total: 0 };
  for (const cat of categories) {
    for (const item of cat.items) {
      counts[item.status] += 1;
      counts.total += 1;
    }
  }
  return counts;
}
