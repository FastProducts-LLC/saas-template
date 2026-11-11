import type {
  CommunityPlan,
  ConversationType,
  MembershipTier,
  SubscriptionStatus,
} from "../../../shared/api/enums";

// Generated backend enums (scripts/gen_enums.py) — never hand-write unions.
export type { CommunityPlan, ConversationType, MembershipTier, SubscriptionStatus };

export interface CommunityProfile {
  id: string;
  handle: string;
  display_name: string;
  bio: string | null;
  avatar_url: string | null;
  created_at: string;
}

export interface CommunityMembershipState {
  tier: MembershipTier;
  subscription_status: SubscriptionStatus;
  is_premium: boolean;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  is_banned: boolean;
}

export interface MyCommunity {
  profile: CommunityProfile | null;
  membership: CommunityMembershipState | null;
}

export interface Member {
  handle: string;
  display_name: string;
  bio: string | null;
  avatar_url: string | null;
  tier: MembershipTier;
  joined_at: string;
}

export interface DirectoryPage {
  items: Member[];
  total: number;
  page: number;
  page_size: number;
}

export interface Plan {
  plan: CommunityPlan;
  name: string;
  price_cents: number;
  interval: string;
  purchasable: boolean;
}

export interface Conversation {
  id: string;
  other: Member | null;
  last_message_preview: string | null;
  last_message_at: string | null;
  unread_count: number;
  created_at: string;
}

export interface Message {
  id: string;
  body: string;
  mine: boolean;
  deleted: boolean;
  created_at: string;
}

export interface MessagePage {
  items: Message[];
  next_before: string | null;
}

export interface JoinPayload {
  handle: string;
  display_name: string;
  bio?: string | null;
  avatar_url?: string | null;
}

export interface ProfileUpdatePayload {
  handle?: string;
  display_name?: string;
  bio?: string | null;
  avatar_url?: string | null;
}
