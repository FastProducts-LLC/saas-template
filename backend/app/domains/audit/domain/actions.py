"""Canonical audit action names — "<slice>.<event>", past tense.

Writers import these instead of inlining strings so the trail stays greppable
and filterable; add new constants here rather than ad-hoc literals.
"""

LOGIN_SUCCEEDED = "auth.login_succeeded"
LOGIN_FAILED = "auth.login_failed"
LOCKOUT_TRIGGERED = "auth.lockout_triggered"
REFRESH_TOKEN_REUSED = "auth.refresh_token_reused"  # noqa: S105 — audit action name, not a secret
PASSWORD_CHANGED = "auth.password_changed"  # noqa: S105 — audit action name, not a secret
PASSWORD_RESET = "auth.password_reset"  # noqa: S105 — audit action name, not a secret
CREDIT_PACK_PURCHASED = "billing.credit_pack_purchased"
COMMUNITY_MEMBER_BANNED = "community.member_banned"
COMMUNITY_MEMBER_UNBANNED = "community.member_unbanned"
COMMUNITY_PROFILE_HIDDEN = "community.profile_hidden"
COMMUNITY_PROFILE_UNHIDDEN = "community.profile_unhidden"

PLAN_SUBSCRIBED = "billing.plan_subscribed"
PLAN_CHANGED = "billing.plan_changed"
PLAN_CANCELED = "billing.plan_canceled"
ENTITLEMENT_OVERRIDE_SET = "entitlements.override_set"
ENTITLEMENT_OVERRIDE_REMOVED = "entitlements.override_removed"
