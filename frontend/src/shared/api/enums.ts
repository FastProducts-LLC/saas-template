// GENERATED FILE — do not edit by hand. Source: backend domain enums (python3 scripts/gen_enums.py)

// backend/app/domains/organizations/domain/entities.py
export type Role = "owner" | "admin" | "member";
export const ROLE_VALUES = ["owner", "admin", "member"] as const;

// backend/app/domains/credits/domain/value_objects.py
export type CreditAction = "image_nano_banana" | "image_gpt" | "video_veo" | "llm_call";
export const CREDIT_ACTION_VALUES = ["image_nano_banana", "image_gpt", "video_veo", "llm_call"] as const;

// backend/app/domains/credits/domain/value_objects.py
export type CreditPack = "starter" | "growth" | "scale" | "bulk";
export const CREDIT_PACK_VALUES = ["starter", "growth", "scale", "bulk"] as const;

// backend/app/domains/credits/domain/value_objects.py
export type ReservationStatus = "pending" | "captured" | "released" | "expired";
export const RESERVATION_STATUS_VALUES = ["pending", "captured", "released", "expired"] as const;

// backend/app/domains/credits/domain/value_objects.py
export type TransactionType = "grant" | "hold" | "release" | "expire" | "adjustment";
export const TRANSACTION_TYPE_VALUES = ["grant", "hold", "release", "expire", "adjustment"] as const;

// backend/app/domains/generations/domain/entities.py
export type GenerationStatus = "pending" | "succeeded" | "failed" | "canceled";
export const GENERATION_STATUS_VALUES = ["pending", "succeeded", "failed", "canceled"] as const;

// backend/app/domains/privacy_requests/domain/entities.py
export type PrivacyRequestStatus = "received" | "verified" | "forwarded" | "fulfilled" | "closed" | "rejected";
export const PRIVACY_REQUEST_STATUS_VALUES = ["received", "verified", "forwarded", "fulfilled", "closed", "rejected"] as const;

// backend/app/domains/blog/domain/entities.py
export type PostStatus = "draft" | "published" | "archived" | "scheduled";
export const POST_STATUS_VALUES = ["draft", "published", "archived", "scheduled"] as const;

// backend/app/domains/community/domain/entities.py
export type MembershipTier = "free" | "premium";
export const MEMBERSHIP_TIER_VALUES = ["free", "premium"] as const;

// backend/app/domains/community/domain/entities.py
export type SubscriptionStatus = "none" | "active" | "past_due" | "canceled";
export const SUBSCRIPTION_STATUS_VALUES = ["none", "active", "past_due", "canceled"] as const;

// backend/app/domains/community/domain/entities.py
export type ConversationType = "dm";
export const CONVERSATION_TYPE_VALUES = ["dm"] as const;

// backend/app/domains/community/domain/value_objects.py
export type CommunityPlan = "monthly" | "annual";
export const COMMUNITY_PLAN_VALUES = ["monthly", "annual"] as const;

// backend/app/domains/billing/domain/value_objects.py
export type Plan = "free" | "pro" | "team";
export const PLAN_VALUES = ["free", "pro", "team"] as const;

// backend/app/domains/billing/domain/value_objects.py
export type BillingInterval = "monthly" | "annual";
export const BILLING_INTERVAL_VALUES = ["monthly", "annual"] as const;

// backend/app/domains/billing/domain/value_objects.py
export type PlanSubscriptionStatus = "incomplete" | "trialing" | "active" | "past_due" | "canceled";
export const PLAN_SUBSCRIPTION_STATUS_VALUES = ["incomplete", "trialing", "active", "past_due", "canceled"] as const;

// backend/app/domains/files/domain/entities.py
export type StoredFileStatus = "pending" | "ready";
export const STORED_FILE_STATUS_VALUES = ["pending", "ready"] as const;

// backend/app/domains/files/domain/entities.py
export type FilePurpose = "avatar";
export const FILE_PURPOSE_VALUES = ["avatar"] as const;

// backend/app/domains/entitlements/domain/entities.py
export type EntitlementKey = "seats" | "api_keys";
export const ENTITLEMENT_KEY_VALUES = ["seats", "api_keys"] as const;
