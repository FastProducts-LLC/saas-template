"""Community domain entities — pure Python, zero framework/ORM imports.

Platform-level (not tenant-scoped): the community hangs off users.id
directly. Free members get a profile and the directory; a premium
subscription (Stripe, managed by the billing slice) unlocks messaging.
"""

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta


def _utcnow() -> datetime:
    return datetime.now(UTC)


class MembershipTier(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"


class SubscriptionStatus(str, enum.Enum):
    NONE = "none"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


class ConversationType(str, enum.Enum):
    # Only DMs today. Groups later add a member-managed type here; messages
    # and participants are already conversation-keyed so nothing else moves.
    DM = "dm"


@dataclass(eq=False)
class CommunityProfile:
    """A member's public face: handle, display name, bio."""

    user_id: uuid.UUID
    handle: str
    display_name: str
    bio: str | None = None
    avatar_url: str | None = None
    # Hidden by a moderator — excluded from the directory and unreachable
    # for new conversations, without deleting anything.
    is_hidden: bool = False
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def touch(self) -> None:
        self.updated_at = _utcnow()


@dataclass(eq=False)
class CommunityMembership:
    """A member's tier + subscription state. One row per user, created on join."""

    user_id: uuid.UUID
    tier: MembershipTier = MembershipTier.FREE
    subscription_status: SubscriptionStatus = SubscriptionStatus.NONE
    # User-level Stripe customer — deliberately separate from the org-keyed
    # BillingAccount; a person may hold both.
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    banned_at: datetime | None = None
    banned_by: uuid.UUID | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    @property
    def is_banned(self) -> bool:
        return self.banned_at is not None

    def is_premium(self, *, grace_days: int, now: datetime | None = None) -> bool:
        """Whether premium features are unlocked right now.

        past_due keeps access for `grace_days` past the paid-through date
        (Stripe retries payment in that window); canceled loses it at once.
        """
        if self.is_banned or self.tier is not MembershipTier.PREMIUM:
            return False
        if self.subscription_status is SubscriptionStatus.ACTIVE:
            return True
        if (
            self.subscription_status is SubscriptionStatus.PAST_DUE
            and self.current_period_end is not None
        ):
            deadline = self.current_period_end + timedelta(days=grace_days)
            return (now or _utcnow()) <= deadline
        return False

    def apply_subscription(
        self,
        *,
        subscription_id: str,
        status: SubscriptionStatus,
        current_period_end: datetime | None,
        cancel_at_period_end: bool,
        customer_id: str | None = None,
    ) -> None:
        if customer_id:
            self.stripe_customer_id = customer_id
        self.stripe_subscription_id = subscription_id
        self.subscription_status = status
        self.current_period_end = current_period_end
        self.cancel_at_period_end = cancel_at_period_end
        if status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE):
            self.tier = MembershipTier.PREMIUM
        else:
            self.tier = MembershipTier.FREE
        self.updated_at = _utcnow()

    def downgrade(self) -> None:
        """Subscription ended (deleted at Stripe) — back to free at once.

        Keeps stripe_customer_id so a resubscribe reuses the same customer.
        """
        self.tier = MembershipTier.FREE
        self.subscription_status = SubscriptionStatus.CANCELED
        self.stripe_subscription_id = None
        self.current_period_end = None
        self.cancel_at_period_end = False
        self.updated_at = _utcnow()

    def ban(self, *, by: uuid.UUID) -> None:
        self.banned_at = _utcnow()
        self.banned_by = by
        self.updated_at = _utcnow()

    def unban(self) -> None:
        self.banned_at = None
        self.banned_by = None
        self.updated_at = _utcnow()


@dataclass(eq=False)
class Conversation:
    """A message thread. DMs are pair-unique via dm_key; a future group
    type sets dm_key to None."""

    type: ConversationType = ConversationType.DM
    dm_key: str | None = None
    created_by: uuid.UUID | None = None
    last_message_at: datetime | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(eq=False)
class ConversationParticipant:
    conversation_id: uuid.UUID
    user_id: uuid.UUID
    last_read_at: datetime | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)

    def mark_read(self) -> None:
        self.last_read_at = _utcnow()


@dataclass(eq=False)
class Message:
    conversation_id: uuid.UUID
    body: str
    # SET NULL on user deletion — the thread keeps its history.
    sender_id: uuid.UUID | None = None
    # Moderation soft-delete: body is masked at the read edge, never returned.
    deleted_at: datetime | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
