"""Application settings, loaded from environment variables (.env in development)."""

import ipaddress
import secrets
from typing import Literal
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core import dev_secrets
from app.core.brand import BRAND_NAME

_INSECURE_SECRET_KEYS = {"", "change-me-in-production", "change-me-generate-a-long-random-string"}
_LOCAL_HOST_SUFFIXES = (".localhost", ".local", ".test", ".internal")


def _is_local_url(url: str) -> bool:
    """True for URLs that can only be a developer machine / private network
    (localhost, loopback, RFC 1918 LAN IPs for device testing, .local/.test)."""
    host = (urlsplit(url).hostname or "").lower()
    if not host or host == "localhost" or host.endswith(_LOCAL_HOST_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return "." not in host  # bare single-label names (docker service names)
    return ip.is_loopback or ip.is_private


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Default comes from shared/brand.toml (gen_brand.py); APP_NAME env overrides.
    app_name: str = BRAND_NAME
    environment: Literal["development", "production"] = "development"

    # Security
    # The placeholder never signs anything: off-localhost the validators
    # refuse to boot, on a local stack it is swapped for a random
    # per-checkout key (app.core.dev_secrets).
    secret_key: str = "change-me-in-production"  # noqa: S105
    # Rotation: move the old SECRET_KEY here when you change it. Tokens signed
    # with it keep verifying (it never signs); remove it once the longest
    # token TTL has passed (EMAIL_VERIFICATION_TTL_HOURS).
    secret_key_previous: str = ""
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    invitation_ttl_days: int = 7
    impersonation_ttl_minutes: int = 15
    # Product policy knobs — flip per project; see docs/customization.md § Security.
    # Domain claim: never squat a company domain before mailbox proof.
    #   off          — never auto-claim; SetOrgDomain disabled
    #   verified_claim — auto-claim on org create only when email_verified (default)
    #   manual_only  — never auto-claim; owners claim via SetOrgDomain after verify
    domain_claim_mode: Literal["off", "verified_claim", "manual_only"] = "verified_claim"
    # Email verification gate for session users (API keys are unaffected):
    #   none      — login + all routes work unverified (dev convenience only)
    #   sensitive — mutating/billing/AI/org-create routes require verified email (default)
    #   login     — block login until verified
    email_verification_gate: Literal["none", "sensitive", "login"] = "sensitive"
    # Signup enumeration protection (verify-first signup). Off: register
    # answers 409 for a taken email and the client signs the new user in at
    # once — smooth, but anyone can test whether an address has an account.
    # On: register answers the same 202 "check your email" either way (an
    # existing owner gets a notice email instead), and sign-in treats an
    # unconfirmed account exactly like a wrong password until the emailed link
    # is used — so register-then-login reveals nothing either. Implies the
    # "login" verification gate. Costs one extra step at signup.
    signup_enumeration_protection: bool = False
    # Login lockout (Redis-backed; degrades to a per-process in-memory
    # counter if Redis is down). Two scopes, both tracked whether or not the
    # account exists, so lockout responses can't be used to enumerate accounts:
    #   * per email + client IP — MAX_ATTEMPTS failures lock only that client,
    #     so someone guessing at an account can't lock its owner out.
    #   * per email, all IPs    — ACCOUNT_MAX_ATTEMPTS failures lock the email
    #     for everyone: the cap on distributed guessing. Keep it well above
    #     MAX_ATTEMPTS (it is the remaining lock-out-the-owner lever; a
    #     password reset lifts it). 0 disables the account-wide lock.
    login_lockout_max_attempts: int = 5
    login_lockout_account_max_attempts: int = 50
    login_lockout_window_minutes: int = 15
    login_lockout_duration_minutes: int = 15
    # Security-event trail (domains/audit) — purged past this age by a beat task.
    audit_retention_days: int = 365

    # Infrastructure
    database_url: str = "postgresql+asyncpg://app:app@localhost:21429/app"
    # Valkey DB 0: app cache / rate limits / error context
    redis_url: str = "redis://localhost:21430/0"

    # Celery — separate Valkey databases to isolate broker churn from app data.
    celery_broker_url: str = "redis://localhost:21430/1"  # Valkey DB 1: task broker
    celery_result_backend: str = "redis://localhost:21430/2"  # Valkey DB 2: task results

    # URLs
    frontend_url: str = "http://localhost:21427"
    cors_origins: list[str] = ["http://localhost:21427"]

    # Email — pluggable provider: "smtp" (Mailpit in development) or "resend".
    # Add SendGrid/SES/etc. by dropping a new provider module into app/core/email/.
    email_provider: Literal["smtp", "resend"] = "smtp"
    email_from: str = "noreply@example.com"
    email_from_name: str = ""  # display name; falls back to app_name
    support_email: str = ""  # reply-to on transactional email when set
    email_verification_ttl_hours: int = 48
    password_reset_ttl_minutes: int = 60

    # SMTP (used when email_provider == "smtp")
    smtp_host: str = "localhost"
    smtp_port: int = 1025

    # Resend (used when email_provider == "resend")
    resend_api_key: str = ""
    resend_segment_marketing: str = ""  # opted-in marketing list (segment/audience id)
    resend_webhook_secret: str = ""  # svix signing secret for /api/webhooks/resend

    # AI providers (generations + llm features) — empty key disables that provider.
    gemini_api_key: str = ""  # nano-banana images + VEO video + Gemini text
    openai_api_key: str = ""  # GPT images + GPT text
    anthropic_api_key: str = ""  # Claude text completions
    # Text-completion model per provider (see domains/llm) — override per project.
    llm_gemini_model: str = "gemini-2.5-flash"
    llm_openai_model: str = "gpt-4.1-mini"
    llm_anthropic_model: str = "claude-sonnet-4-6"
    # Generated assets root. Relative paths resolve against the backend
    # workdir (/app in Docker); backend and worker must share this directory.
    media_dir: str = "media"

    # Object storage: local disk by default, or an S3-compatible bucket.
    storage_provider: Literal["local", "s3"] = "local"
    s3_bucket: str = ""
    s3_region: str = ""
    s3_endpoint_url: str = ""  # empty = AWS; set for DigitalOcean Spaces
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""

    # Observability — error tracking is a no-op unless SENTRY_DSN is set.
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # One-time credit packs (mode=payment) — empty id disables that pack.
    stripe_price_credits_starter: str = ""
    stripe_price_credits_growth: str = ""
    stripe_price_credits_scale: str = ""
    stripe_price_credits_bulk: str = ""
    # Community membership subscriptions (mode=subscription) — empty id
    # disables that plan.
    stripe_price_community_monthly: str = ""
    stripe_price_community_annual: str = ""
    # Organization subscription plans — empty id disables that plan/interval.
    stripe_price_plan_pro_monthly: str = ""
    stripe_price_plan_pro_annual: str = ""
    stripe_price_plan_team_monthly: str = ""
    stripe_price_plan_team_annual: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_local_dev(self) -> bool:
        """Development mode AND only reachable on a developer machine/LAN.
        Dev-only conveniences that weaken security key off this, not off
        ENVIRONMENT alone (which defaults to development when unset)."""
        return not self.is_production and all(
            _is_local_url(u) for u in (self.frontend_url, *self.cors_origins)
        )

    @property
    def token_issuer(self) -> str:
        """JWT `iss` — pins tokens to this deployment."""
        return self.frontend_url.rstrip("/")

    @property
    def email_sender(self) -> str:
        """RFC 5322 sender, e.g. 'AppName <noreply@example.com>'."""
        return f"{self.email_from_name or self.app_name} <{self.email_from}>"

    @model_validator(mode="after")
    def _guard_s3_configuration(self) -> "Settings":
        if self.storage_provider == "s3":
            for name in ("s3_bucket", "s3_region", "s3_access_key_id", "s3_secret_access_key"):
                if not getattr(self, name).strip():
                    raise ValueError(f"{name.upper()} must be set when STORAGE_PROVIDER=s3.")
        return self

    @model_validator(mode="after")
    def _guard_placeholder_secret_off_localhost(self) -> "Settings":
        """ENVIRONMENT defaults to "development", so a deploy that forgets to
        set it would skip the production guard below and sign every JWT with
        the publicly known placeholder. Catch that case by evidence instead of
        by the flag: a placeholder SECRET_KEY is only tolerated when everything
        points at a local machine — and even there it is never used: the dev
        API port is published on the LAN, so tokens are signed with a random
        per-checkout key instead."""
        if self.secret_key_previous and self.secret_key_previous in _INSECURE_SECRET_KEYS:
            raise ValueError(
                "SECRET_KEY_PREVIOUS is a placeholder — it still verifies tokens, so "
                "anyone could forge one. Leave it empty unless you are rotating keys."
            )
        if self.is_production or self.secret_key not in _INSECURE_SECRET_KEYS:
            return self
        public_urls = [u for u in (self.frontend_url, *self.cors_origins) if not _is_local_url(u)]
        live_stripe = self.stripe_secret_key.startswith(("sk_live_", "rk_live_"))
        if public_urls or live_stripe:
            evidence = public_urls[0] if public_urls else "a live Stripe key"
            raise ValueError(
                f"SECRET_KEY is still the placeholder but this looks like a real deployment "
                f"({evidence}). Set a strong SECRET_KEY — and ENVIRONMENT=production, which "
                "enables the full production safety checks."
            )
        self.secret_key = dev_secrets.load_or_create(
            "secret_key", lambda: secrets.token_urlsafe(64)
        )
        return self

    @model_validator(mode="after")
    def _guard_production_config(self) -> "Settings":
        """Fail closed: never let production boot on insecure defaults."""
        if not self.is_production:
            return self
        if self.secret_key in _INSECURE_SECRET_KEYS or len(self.secret_key) < 32:
            raise ValueError(
                "SECRET_KEY must be a strong random value (>= 32 bytes) in production. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        if self.secret_key_previous and (
            self.secret_key_previous in _INSECURE_SECRET_KEYS or len(self.secret_key_previous) < 32
        ):
            raise ValueError(
                "SECRET_KEY_PREVIOUS must be a real former SECRET_KEY (>= 32 bytes) — "
                "a placeholder there would let anyone forge tokens."
            )
        if self.stripe_secret_key and not self.stripe_webhook_secret:
            raise ValueError(
                "STRIPE_WEBHOOK_SECRET must be set when Stripe is configured, "
                "otherwise the billing webhook accepts unsigned requests."
            )
        if self.email_provider == "resend" and not self.resend_api_key:
            raise ValueError("RESEND_API_KEY must be set when EMAIL_PROVIDER=resend.")
        if self.email_provider == "resend" and not self.resend_webhook_secret:
            raise ValueError(
                "RESEND_WEBHOOK_SECRET must be set when EMAIL_PROVIDER=resend in production, "
                "otherwise bounce/complaint suppression cannot verify webhook signatures."
            )
        if any("localhost" in origin or "127.0.0.1" in origin for origin in self.cors_origins):
            raise ValueError(
                "CORS_ORIGINS still contains a localhost origin in production — "
                "set it to the real frontend origin(s) in .env.prod."
            )
        return self


settings = Settings()
