// GENERATED FILE — do not edit by hand. Source: shared/events.toml (python3 scripts/gen_events.py)
//
// Call sites: track(EVENTS.<name>, params). CLIENT_EVENTS are the only names
// the first-party ingest accepts; SERVER_EVENTS are listed for reference and
// are written by the backend only — never track() them from the browser.

export const CLIENT_EVENTS = {
  // Landing/pricing call-to-action clicked. Anonymous, so GA-only in practice. (params: cta, location)
  cta_clicked: "cta_clicked",
  // A guided product tour was walked to its last step. tour: dashboard. (params: tour)
  onboarding_tour_completed: "onboarding_tour_completed",
  // A guided product tour was dismissed before the end. tour: dashboard. (params: tour)
  onboarding_tour_skipped: "onboarding_tour_skipped",
  // Registration form rendered. Anonymous, so GA-only in practice. (params: none)
  signup_started: "signup_started",
  // Registration succeeded and the new session is live. (params: method, marketing_opt_in)
  user_signed_up: "user_signed_up",
  // Interactive login succeeded (not silent session restore). (params: method)
  user_logged_in: "user_logged_in",
  // Logout requested. Fired just before the logout call, while the session can still authenticate the event. (params: none)
  user_logged_out: "user_logged_out",
  // Forgot-password form submitted. Anonymous, so GA-only in practice. (params: none)
  password_reset_requested: "password_reset_requested",
  // Stripe Checkout session created, just before the redirect. product: credit_pack | community. (params: product, plan)
  checkout_started: "checkout_started",
  // Stripe billing portal session created. product: credits | community. (params: product)
  billing_portal_opened: "billing_portal_opened",
  // Organization created. (params: none)
  org_created: "org_created",
  // Teammate invitation created. (params: role)
  invite_sent: "invite_sent",
  // Invitation accepted; the user joined an organization. (params: none)
  invite_accepted: "invite_accepted",
  // API key issued. (params: none)
  api_key_created: "api_key_created",
  // API key revoked. (params: none)
  api_key_revoked: "api_key_revoked",
  // A settings form saved. section: profile_name | password | marketing | org_name | org_domain. (params: section)
  settings_updated: "settings_updated",
  // Community profile created (member joined the directory). (params: none)
  community_joined: "community_joined",
  // Community profile edited. (params: none)
  community_profile_updated: "community_profile_updated",
  // New 1:1 conversation opened with another member. (params: none)
  community_conversation_started: "community_conversation_started",
  // Direct message sent. Never carries the body or recipient. (params: none)
  community_message_sent: "community_message_sent",
  // Organization plan checkout session created, just before the redirect. (params: plan, interval)
  plan_checkout_started: "plan_checkout_started",
  // Avatar upload confirmed successfully. Never carries the file URL or filename. (params: file_id)
  avatar_uploaded: "avatar_uploaded",
} as const;

export const SERVER_EVENTS = {
  // checkout.session.completed for a credit pack, first delivery only (after the grant). (params: pack, credits, amount_cents)
  credit_pack_purchased: "credit_pack_purchased",
  // Community membership became premium via Stripe (transition only, not redelivery). (params: none)
  community_subscription_activated: "community_subscription_activated",
  // Community subscription deleted at Stripe; membership back to free. (params: none)
  community_subscription_canceled: "community_subscription_canceled",
  // AI generation accepted and credits held (web, mobile, and API callers alike). (params: kind, credits_cost)
  generation_requested: "generation_requested",
  // ACTIVATION. AI generation delivered and its credit hold captured. (params: kind, credits_cost, duration_ms)
  generation_completed: "generation_completed",
  // AI generation failed at the provider; credits released. (params: kind)
  generation_failed: "generation_failed",
  // Metered text completion delivered and its credit hold captured. (params: provider, credits_cost)
  llm_call_completed: "llm_call_completed",
  // Organization acquired a paid subscription; emitted once for the transition. (params: organization_id, plan, interval)
  plan_subscribed: "plan_subscribed",
  // Organization subscription plan or billing interval changed. (params: organization_id, plan, interval)
  plan_changed: "plan_changed",
  // Organization subscription canceled at the payment provider. (params: organization_id, plan)
  plan_canceled: "plan_canceled",
} as const;

/** Merged view for call sites and the registry audit. */
export const EVENTS = { ...CLIENT_EVENTS, ...SERVER_EVENTS } as const;

export type ClientEvent = (typeof CLIENT_EVENTS)[keyof typeof CLIENT_EVENTS];
export type ServerEvent = (typeof SERVER_EVENTS)[keyof typeof SERVER_EVENTS];
export type AnalyticsEvent = ClientEvent | ServerEvent;

/** GA4 recommended-event names for registry events that have one. The
 *  first-party table always stores the registry name. */
export const GA_EVENT_ALIASES: Partial<Record<ClientEvent, string>> = {
  signup_started: "sign_up_start",
  user_signed_up: "sign_up",
  user_logged_in: "login",
  checkout_started: "begin_checkout",
};
