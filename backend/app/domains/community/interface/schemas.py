"""Community HTTP schemas — Pydantic at the edge only."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, field_validator

from app.core.policy import (
    COMMUNITY_AVATAR_URL_MAX_LENGTH,
    COMMUNITY_BIO_MAX_LENGTH,
    COMMUNITY_DISPLAY_NAME_MAX_LENGTH,
    COMMUNITY_HANDLE_MAX_LENGTH,
    COMMUNITY_MESSAGE_MAX_LENGTH,
    COMMUNITY_PREMIUM_GRACE_DAYS,
)
from app.domains.community.application.dtos import ConversationSummary
from app.domains.community.domain.entities import (
    CommunityMembership,
    CommunityProfile,
    MembershipTier,
    Message,
)

_PREVIEW_LENGTH = 140

MembershipTierLiteral = Literal["free", "premium"]
SubscriptionStatusLiteral = Literal["none", "active", "past_due", "canceled"]

# Accepts any case; the use case lowercases via normalize_handle.
HANDLE_PATTERN = r"^[A-Za-z0-9_]{3,30}$"


def _https_url_only(value: str | None) -> str | None:
    """Scheme allow-list for user-supplied image URLs: https only. Rejects
    javascript:/data:/file: and plain http (mixed content) at the edge rather
    than relying on every renderer (web, mobile, email) to be safe."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not value.lower().startswith("https://") or any(c.isspace() for c in value):
        raise ValueError("Avatar URL must be an https:// link.")
    return value


AvatarUrl = Annotated[
    str | None,
    Field(default=None, max_length=COMMUNITY_AVATAR_URL_MAX_LENGTH),
    AfterValidator(_https_url_only),
]


class ProfileCreate(BaseModel):
    handle: str = Field(pattern=HANDLE_PATTERN, max_length=COMMUNITY_HANDLE_MAX_LENGTH)
    display_name: str = Field(min_length=1, max_length=COMMUNITY_DISPLAY_NAME_MAX_LENGTH)
    bio: str | None = Field(default=None, max_length=COMMUNITY_BIO_MAX_LENGTH)
    avatar_url: AvatarUrl = None


class ProfileUpdate(BaseModel):
    """Partial update — only fields the client sends are applied."""

    handle: str | None = Field(
        default=None, pattern=HANDLE_PATTERN, max_length=COMMUNITY_HANDLE_MAX_LENGTH
    )
    display_name: str | None = Field(
        default=None, min_length=1, max_length=COMMUNITY_DISPLAY_NAME_MAX_LENGTH
    )
    bio: str | None = Field(default=None, max_length=COMMUNITY_BIO_MAX_LENGTH)
    avatar_url: AvatarUrl = None


class AvatarUpdate(BaseModel):
    file_id: uuid.UUID


class ProfileOut(BaseModel):
    id: uuid.UUID
    handle: str
    display_name: str
    bio: str | None
    avatar_url: str | None
    created_at: datetime

    @classmethod
    def from_entity(cls, profile: CommunityProfile) -> "ProfileOut":
        return cls(
            id=profile.id,
            handle=profile.handle,
            display_name=profile.display_name,
            bio=profile.bio,
            avatar_url=profile.avatar_url,
            created_at=profile.created_at,
        )


class MembershipOut(BaseModel):
    tier: MembershipTierLiteral
    subscription_status: SubscriptionStatusLiteral
    is_premium: bool
    current_period_end: datetime | None
    cancel_at_period_end: bool
    is_banned: bool

    @classmethod
    def from_entity(cls, membership: CommunityMembership) -> "MembershipOut":
        return cls(
            tier=membership.tier.value,  # type: ignore[arg-type]
            subscription_status=membership.subscription_status.value,  # type: ignore[arg-type]
            is_premium=membership.is_premium(grace_days=COMMUNITY_PREMIUM_GRACE_DAYS),
            current_period_end=membership.current_period_end,
            cancel_at_period_end=membership.cancel_at_period_end,
            is_banned=membership.is_banned,
        )


class MyCommunityOut(BaseModel):
    """null profile means "not joined yet" — the frontend shows the join
    screen, not an error state."""

    profile: ProfileOut | None
    membership: MembershipOut | None


class MemberOut(BaseModel):
    """Public directory card — never exposes user_id or moderation state."""

    handle: str
    display_name: str
    bio: str | None
    avatar_url: str | None
    tier: MembershipTierLiteral
    joined_at: datetime

    @classmethod
    def from_row(cls, profile: CommunityProfile, tier: MembershipTier) -> "MemberOut":
        return cls(
            handle=profile.handle,
            display_name=profile.display_name,
            bio=profile.bio,
            avatar_url=profile.avatar_url,
            tier=tier.value,  # type: ignore[arg-type]
            joined_at=profile.created_at,
        )


class DirectoryPage(BaseModel):
    items: list[MemberOut]
    total: int
    page: int
    page_size: int


class StartConversationRequest(BaseModel):
    recipient_handle: str = Field(pattern=HANDLE_PATTERN, max_length=COMMUNITY_HANDLE_MAX_LENGTH)


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=COMMUNITY_MESSAGE_MAX_LENGTH)

    @field_validator("body")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message body can't be blank.")
        return value


class MessageOut(BaseModel):
    id: uuid.UUID
    # Moderation-deleted bodies never leave the API.
    body: str
    mine: bool
    deleted: bool
    created_at: datetime

    @classmethod
    def from_entity(cls, message: Message, *, viewer_id: uuid.UUID) -> "MessageOut":
        return cls(
            id=message.id,
            body="" if message.is_deleted else message.body,
            mine=message.sender_id == viewer_id,
            deleted=message.is_deleted,
            created_at=message.created_at,
        )


class MessagePage(BaseModel):
    """Newest first. Pass the last item's id as ?before= for the next
    (older) page; next_before is null when this page is the end."""

    items: list[MessageOut]
    next_before: uuid.UUID | None


class ConversationOut(BaseModel):
    id: uuid.UUID
    # None when the other account was deleted.
    other: MemberOut | None
    last_message_preview: str | None
    last_message_at: datetime | None
    unread_count: int
    created_at: datetime

    @classmethod
    def from_summary(cls, summary: ConversationSummary) -> "ConversationOut":
        last = summary.last_message
        preview = None
        if last is not None:
            preview = "" if last.is_deleted else last.body[:_PREVIEW_LENGTH]
        return cls(
            id=summary.conversation.id,
            other=(
                MemberOut(
                    handle=summary.other.handle,
                    display_name=summary.other.display_name,
                    bio=summary.other.bio,
                    avatar_url=summary.other.avatar_url,
                    tier="free",  # tier isn't surfaced in conversation lists
                    joined_at=summary.other.created_at,
                )
                if summary.other
                else None
            ),
            last_message_preview=preview,
            last_message_at=summary.conversation.last_message_at,
            unread_count=summary.unread_count,
            created_at=summary.conversation.created_at,
        )


CommunityPlanLiteral = Literal["monthly", "annual"]


class MembershipCheckoutRequest(BaseModel):
    plan: CommunityPlanLiteral


class PlanOut(BaseModel):
    plan: CommunityPlanLiteral
    name: str
    price_cents: int
    interval: str
    purchasable: bool


class RedirectOut(BaseModel):
    url: str


class AdminCommunityMemberOut(BaseModel):
    """Superuser moderation row — includes hidden/banned state and email."""

    user_id: uuid.UUID
    handle: str
    display_name: str
    email: str
    tier: MembershipTierLiteral
    subscription_status: SubscriptionStatusLiteral
    is_hidden: bool
    is_banned: bool
    banned_at: datetime | None
    joined_at: datetime

    @classmethod
    def from_row(
        cls,
        profile: CommunityProfile,
        membership: CommunityMembership,
        email: str,
    ) -> "AdminCommunityMemberOut":
        return cls(
            user_id=profile.user_id,
            handle=profile.handle,
            display_name=profile.display_name,
            email=email,
            tier=membership.tier.value,  # type: ignore[arg-type]
            subscription_status=membership.subscription_status.value,  # type: ignore[arg-type]
            is_hidden=profile.is_hidden,
            is_banned=membership.is_banned,
            banned_at=membership.banned_at,
            joined_at=profile.created_at,
        )


class AdminCommunityMemberPage(BaseModel):
    items: list[AdminCommunityMemberOut]
    total: int
    page: int
    page_size: int
