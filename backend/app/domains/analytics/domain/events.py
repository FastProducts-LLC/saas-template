"""GENERATED FILE — do not edit by hand.

Source: shared/events.toml (python3 scripts/gen_events.py)

CLIENT_EVENTS is the POST /api/events allowlist; SERVER_EVENTS are the only
names capture_server_event() will write.
"""

# Browser-originated events (source='client').
CLIENT_EVENTS: frozenset[str] = frozenset(
    {
        "api_key_created",
        "api_key_revoked",
        "avatar_uploaded",
        "billing_portal_opened",
        "checkout_started",
        "community_conversation_started",
        "community_joined",
        "community_message_sent",
        "community_profile_updated",
        "cta_clicked",
        "invite_accepted",
        "invite_sent",
        "onboarding_tour_completed",
        "onboarding_tour_skipped",
        "org_created",
        "password_reset_requested",
        "plan_checkout_started",
        "settings_updated",
        "signup_started",
        "user_logged_in",
        "user_logged_out",
        "user_signed_up",
    }
)

# Backend-originated truth events (source='server').
SERVER_EVENTS: frozenset[str] = frozenset(
    {
        "community_subscription_activated",
        "community_subscription_canceled",
        "credit_pack_purchased",
        "generation_completed",
        "generation_failed",
        "generation_requested",
        "llm_call_completed",
        "plan_canceled",
        "plan_changed",
        "plan_subscribed",
    }
)
