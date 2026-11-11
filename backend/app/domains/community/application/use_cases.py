"""Community use cases — profiles, directory, membership state, and the
premium-subscription lifecycle."""

import logging
import uuid
from datetime import datetime
from typing import Any

from app.domains.audit.domain import AuditEvent
from app.domains.audit.domain import actions as audit_actions
from app.domains.auth.domain import User
from app.domains.billing.domain import (
    BillingNotConfigured,
    CommunityPlanNotConfigured,
    NoBillingAccount,
)
from app.domains.community.application.dtos import ConversationSummary
from app.domains.community.application.ports import (
    ActivityTracker,
    AuditRecorder,
    CommunityMembershipRepository,
    CommunityPaymentGateway,
    CommunityProfileRepository,
    ConversationRepository,
    FileService,
    MessageRepository,
)
from app.domains.community.domain.entities import (
    CommunityMembership,
    CommunityProfile,
    Conversation,
    MembershipTier,
    Message,
    SubscriptionStatus,
)
from app.domains.community.domain.errors import (
    AlreadyPremium,
    CannotMessageSelf,
    CommunityBanned,
    ConversationNotFound,
    HandleTaken,
    NotACommunityMember,
    PremiumRequired,
    ProfileNotFound,
    RecipientUnavailable,
)
from app.domains.community.domain.services import dm_key, normalize_handle
from app.domains.community.domain.value_objects import COMMUNITY_PLANS, CommunityPlan
from app.domains.files.domain.entities import FilePurpose
from app.domains.files.domain.errors import FileNotFound

logger = logging.getLogger(__name__)


def _require_active_member(
    profile: CommunityProfile | None, membership: CommunityMembership | None
) -> tuple[CommunityProfile, CommunityMembership]:
    if profile is None or membership is None:
        raise NotACommunityMember("You need to join the community first.")
    if membership.is_banned:
        raise CommunityBanned("Your community access has been suspended.")
    return profile, membership


class JoinCommunity:
    """Create the free profile + membership pair. Idempotent: joining again
    returns the existing profile unchanged."""

    def __init__(
        self,
        profiles: CommunityProfileRepository,
        memberships: CommunityMembershipRepository,
    ) -> None:
        self.profiles = profiles
        self.memberships = memberships

    async def execute(
        self,
        user_id: uuid.UUID,
        *,
        handle: str,
        display_name: str,
        bio: str | None,
        avatar_url: str | None,
    ) -> tuple[CommunityProfile, CommunityMembership]:
        membership = await self.memberships.get_by_user(user_id)
        if membership is not None and membership.is_banned:
            raise CommunityBanned("Your community access has been suspended.")

        existing = await self.profiles.get_by_user(user_id)
        if existing is not None:
            if membership is None:  # created together on join; never expected
                raise RuntimeError("community profile exists without a membership")
            return existing, membership

        final_handle = normalize_handle(handle)
        if not final_handle:
            raise HandleTaken("Handles are 3-30 characters: a-z, 0-9, underscores.")
        if await self.profiles.get_by_handle(final_handle):
            raise HandleTaken("Someone already uses this handle.")

        profile = CommunityProfile(
            user_id=user_id,
            handle=final_handle,
            display_name=display_name.strip(),
            bio=bio,
            avatar_url=avatar_url,
        )
        await self.profiles.add(profile)
        if membership is None:
            membership = CommunityMembership(user_id=user_id)
            await self.memberships.add(membership)
        return profile, membership


class UpdateMyProfile:
    """Partial update. `updates` holds only the fields the caller sent."""

    def __init__(
        self,
        profiles: CommunityProfileRepository,
        memberships: CommunityMembershipRepository,
        files: FileService | None = None,
    ) -> None:
        self.profiles = profiles
        self.memberships = memberships
        self.files = files

    async def execute(self, user_id: uuid.UUID, *, updates: dict[str, Any]) -> CommunityProfile:
        profile, _ = _require_active_member(
            await self.profiles.get_by_user(user_id),
            await self.memberships.get_by_user(user_id),
        )

        if "handle" in updates:
            new_handle = normalize_handle(str(updates["handle"]))
            if not new_handle:
                raise HandleTaken("Handles are 3-30 characters: a-z, 0-9, underscores.")
            if new_handle != profile.handle:
                other = await self.profiles.get_by_handle(new_handle)
                if other is not None and other.id != profile.id:
                    raise HandleTaken("Someone already uses this handle.")
                profile.handle = new_handle
        if "display_name" in updates:
            profile.display_name = str(updates["display_name"]).strip()
        for attr in ("bio", "avatar_url"):
            if attr in updates:
                setattr(profile, attr, updates[attr])

        if self.files is not None and "avatar_url" in updates:
            await self.files.delete_owner_files(user_id, FilePurpose.AVATAR, keep=None)
        profile.touch()
        return profile


class UpdateMyAvatar:
    """Set an owned, confirmed avatar or clear it, cleaning up other uploads."""

    def __init__(
        self,
        profiles: CommunityProfileRepository,
        memberships: CommunityMembershipRepository,
        files: FileService,
    ) -> None:
        self.profiles = profiles
        self.memberships = memberships
        self.files = files

    async def execute(self, user_id: uuid.UUID, file_id: uuid.UUID | None) -> CommunityProfile:
        profile, _ = _require_active_member(
            await self.profiles.get_by_user(user_id),
            await self.memberships.get_by_user(user_id),
        )
        url = None
        if file_id is not None:
            file = await self.files.get_ready_file(file_id)
            if file is None or file.purpose != FilePurpose.AVATAR or file.user_id != user_id:
                raise FileNotFound()
            url = self.files.content_url(file)
        profile.avatar_url = url
        profile.touch()
        await self.files.delete_owner_files(user_id, FilePurpose.AVATAR, keep=file_id)
        return profile


class GetMyCommunityState:
    """Profile + membership in one call; (None, None) means "not joined yet"
    — the frontend shows the join screen, not an error."""

    def __init__(
        self,
        profiles: CommunityProfileRepository,
        memberships: CommunityMembershipRepository,
    ) -> None:
        self.profiles = profiles
        self.memberships = memberships

    async def execute(
        self, user_id: uuid.UUID
    ) -> tuple[CommunityProfile | None, CommunityMembership | None]:
        return (
            await self.profiles.get_by_user(user_id),
            await self.memberships.get_by_user(user_id),
        )


class ListDirectory:
    """Paginated visible members (hidden profiles and banned members excluded)."""

    def __init__(self, profiles: CommunityProfileRepository) -> None:
        self.profiles = profiles

    async def execute(
        self, *, search: str | None, limit: int, offset: int
    ) -> tuple[list[tuple[CommunityProfile, MembershipTier]], int]:
        return await self.profiles.list_directory(
            search=(search or "").strip() or None, limit=limit, offset=offset
        )


class GetMemberByHandle:
    """Public member card — hidden/banned members 404 like they don't exist."""

    def __init__(self, profiles: CommunityProfileRepository) -> None:
        self.profiles = profiles

    async def execute(self, handle: str) -> tuple[CommunityProfile, MembershipTier]:
        found = await self.profiles.get_visible_by_handle(normalize_handle(handle))
        if found is None:
            raise ProfileNotFound("We couldn't find that community member.")
        return found


class CreateCommunityCheckout:
    """Recurring (mode=subscription) checkout for the premium tier. The
    membership upgrade itself happens when the webhook events land."""

    def __init__(
        self,
        memberships: CommunityMembershipRepository,
        gateway: CommunityPaymentGateway,
        *,
        grace_days: int,
    ) -> None:
        self.memberships = memberships
        self.gateway = gateway
        self.grace_days = grace_days

    async def execute(self, user: User, plan: CommunityPlan) -> str:
        if not self.gateway.is_configured():
            raise BillingNotConfigured("Stripe is not configured (STRIPE_SECRET_KEY).")
        if plan not in COMMUNITY_PLANS or not self.gateway.is_community_plan_purchasable(plan):
            raise CommunityPlanNotConfigured(
                f"Community plan '{plan.value}' has no Stripe price configured."
            )

        membership = await self.memberships.get_by_user(user.id)
        if membership is None:
            raise NotACommunityMember("You need to join the community first.")
        if membership.is_banned:
            raise CommunityBanned("Your community access has been suspended.")
        if membership.is_premium(grace_days=self.grace_days):
            raise AlreadyPremium("You already have an active premium membership.")

        if not membership.stripe_customer_id:
            membership.stripe_customer_id = await self.gateway.create_customer_for_user(
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip(),
                user_id=str(user.id),
            )
        return await self.gateway.create_community_subscription_checkout_url(
            customer_id=membership.stripe_customer_id,
            plan=plan,
            user_id=str(user.id),
        )


class CreateCommunityPortal:
    """Stripe customer portal for managing/canceling the membership."""

    def __init__(
        self,
        memberships: CommunityMembershipRepository,
        gateway: CommunityPaymentGateway,
    ) -> None:
        self.memberships = memberships
        self.gateway = gateway

    async def execute(self, user_id: uuid.UUID) -> str:
        if not self.gateway.is_configured():
            raise BillingNotConfigured("Stripe is not configured (STRIPE_SECRET_KEY).")
        membership = await self.memberships.get_by_user(user_id)
        if membership is None:
            raise NotACommunityMember("You need to join the community first.")
        if not membership.stripe_customer_id:
            raise NoBillingAccount("This membership has no billing history yet.")
        return await self.gateway.create_portal_url(customer_id=membership.stripe_customer_id)


class ApplyCommunitySubscriptionEvent:
    """Webhook-side membership updates — satisfies billing's
    CommunityMembershipService port structurally. Every method no-ops on
    unknown ids, so Stripe redelivery and unrelated subscriptions are safe."""

    def __init__(
        self,
        memberships: CommunityMembershipRepository,
        analytics: ActivityTracker | None = None,
    ) -> None:
        self.memberships = memberships
        self.analytics = analytics

    async def _track_tier_change(self, membership: CommunityMembership, was_premium: bool) -> None:
        """Emit the subscription analytics event on a tier TRANSITION only.

        Stripe delivers at least once and out of order (subscription.created
        can land before checkout.session.completed, `canceled` status before
        subscription.deleted), so "which handler ran" says nothing — only the
        free<->premium edge is a fact worth one event."""
        if self.analytics is None:
            return
        is_premium = membership.tier == MembershipTier.PREMIUM
        if is_premium and not was_premium:
            await self.analytics.capture_server_event(
                membership.user_id, "community_subscription_activated"
            )
        elif was_premium and not is_premium:
            await self.analytics.capture_server_event(
                membership.user_id, "community_subscription_canceled"
            )

    async def activate(
        self,
        *,
        user_id: uuid.UUID,
        stripe_customer_id: str,
        subscription_id: str,
    ) -> None:
        membership = await self.memberships.get_by_user(user_id)
        if membership is None:
            logger.warning(
                "community subscription %s activated for unknown user %s",
                subscription_id,
                user_id,
            )
            return
        was_premium = membership.tier == MembershipTier.PREMIUM
        membership.apply_subscription(
            subscription_id=subscription_id,
            status=SubscriptionStatus.ACTIVE,
            # Preserved if a subscription.created/updated sync already landed.
            current_period_end=membership.current_period_end,
            cancel_at_period_end=membership.cancel_at_period_end,
            customer_id=stripe_customer_id,
        )
        await self._track_tier_change(membership, was_premium)

    async def sync(
        self,
        *,
        subscription_id: str,
        status: SubscriptionStatus,
        current_period_end: datetime | None,
        cancel_at_period_end: bool,
        user_id: uuid.UUID | None,
    ) -> None:
        membership = await self.memberships.get_by_subscription_id(subscription_id)
        if membership is None and user_id is not None:
            # subscription.created can outrace checkout.session.completed —
            # fall back to the user id stamped in subscription metadata, but
            # never steal a membership already tied to another subscription.
            candidate = await self.memberships.get_by_user(user_id)
            if candidate is not None and candidate.stripe_subscription_id in (
                None,
                subscription_id,
            ):
                membership = candidate
        if membership is None:
            return
        was_premium = membership.tier == MembershipTier.PREMIUM
        membership.apply_subscription(
            subscription_id=subscription_id,
            status=status,
            current_period_end=current_period_end,
            cancel_at_period_end=cancel_at_period_end,
        )
        await self._track_tier_change(membership, was_premium)

    async def end(self, *, subscription_id: str) -> None:
        membership = await self.memberships.get_by_subscription_id(subscription_id)
        if membership is None:
            return
        was_premium = membership.tier == MembershipTier.PREMIUM
        membership.downgrade()
        await self._track_tier_change(membership, was_premium)


class _MessagingGate:
    """Shared checks for messaging use cases: joined, not banned, and (for
    send paths) premium."""

    def __init__(self, memberships: CommunityMembershipRepository, *, grace_days: int) -> None:
        self.memberships = memberships
        self.grace_days = grace_days

    async def require_member(self, user_id: uuid.UUID) -> CommunityMembership:
        membership = await self.memberships.get_by_user(user_id)
        if membership is None:
            raise NotACommunityMember("You need to join the community first.")
        if membership.is_banned:
            raise CommunityBanned("Your community access has been suspended.")
        return membership

    async def require_premium(self, user_id: uuid.UUID) -> CommunityMembership:
        membership = await self.require_member(user_id)
        if not membership.is_premium(grace_days=self.grace_days):
            raise PremiumRequired("Messaging is part of the premium membership.")
        return membership


class StartConversation:
    """Get-or-create the DM thread with another member. Premium-gated:
    starting a conversation is sending intent."""

    def __init__(
        self,
        profiles: CommunityProfileRepository,
        conversations: ConversationRepository,
        gate: _MessagingGate,
    ) -> None:
        self.profiles = profiles
        self.conversations = conversations
        self.gate = gate

    async def execute(
        self, user_id: uuid.UUID, *, recipient_handle: str
    ) -> tuple[Conversation, CommunityProfile]:
        await self.gate.require_premium(user_id)

        found = await self.profiles.get_visible_by_handle(normalize_handle(recipient_handle))
        if found is None:
            raise RecipientUnavailable("That member can't receive messages right now.")
        recipient, _ = found
        if recipient.user_id == user_id:
            raise CannotMessageSelf("You can't start a conversation with yourself.")

        key = dm_key(user_id, recipient.user_id)
        conversation = await self.conversations.get_by_dm_key(key)
        if conversation is None:
            conversation = await self.conversations.create_dm(
                dm_key=key,
                created_by=user_id,
                participant_ids=(user_id, recipient.user_id),
            )
        return conversation, recipient


class SendMessage:
    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        gate: _MessagingGate,
    ) -> None:
        self.conversations = conversations
        self.messages = messages
        self.gate = gate

    async def execute(
        self, user_id: uuid.UUID, conversation_id: uuid.UUID, *, body: str
    ) -> Message:
        await self.gate.require_premium(user_id)
        found = await self.conversations.get_for_participant(conversation_id, user_id)
        if found is None:
            raise ConversationNotFound("We couldn't find that conversation.")
        conversation, participant = found

        message = Message(conversation_id=conversation.id, body=body.strip(), sender_id=user_id)
        await self.messages.add(message)
        conversation.last_message_at = message.created_at
        # Your own message never counts as unread.
        participant.last_read_at = message.created_at
        return message


class ListConversations:
    """Free members can read what they've received — only sending is gated."""

    def __init__(self, conversations: ConversationRepository, gate: _MessagingGate) -> None:
        self.conversations = conversations
        self.gate = gate

    async def execute(self, user_id: uuid.UUID) -> list[ConversationSummary]:
        await self.gate.require_member(user_id)
        return await self.conversations.list_for_user(user_id)


class ListMessages:
    """Keyset pagination, newest first: pass the oldest already-loaded
    message id as `before` to fetch the previous page."""

    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        gate: _MessagingGate,
    ) -> None:
        self.conversations = conversations
        self.messages = messages
        self.gate = gate

    async def execute(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        *,
        before_id: uuid.UUID | None,
        limit: int,
    ) -> list[Message]:
        await self.gate.require_member(user_id)
        if await self.conversations.get_for_participant(conversation_id, user_id) is None:
            raise ConversationNotFound("We couldn't find that conversation.")

        anchor: Message | None = None
        if before_id is not None:
            anchor = await self.messages.get(before_id)
            if anchor is None or anchor.conversation_id != conversation_id:
                raise ConversationNotFound("We couldn't find that conversation.")
        return await self.messages.list_page(conversation_id, before=anchor, limit=limit)


class MarkConversationRead:
    def __init__(self, conversations: ConversationRepository, gate: _MessagingGate) -> None:
        self.conversations = conversations
        self.gate = gate

    async def execute(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
        await self.gate.require_member(user_id)
        found = await self.conversations.get_for_participant(conversation_id, user_id)
        if found is None:
            raise ConversationNotFound("We couldn't find that conversation.")
        _, participant = found
        participant.mark_read()


class ListCommunityMembersAdmin:
    """Superuser view: every member incl. hidden/banned, with account email."""

    def __init__(self, profiles: CommunityProfileRepository) -> None:
        self.profiles = profiles

    async def execute(self, *, search: str | None, limit: int, offset: int):
        return await self.profiles.list_admin(
            search=(search or "").strip() or None, limit=limit, offset=offset
        )


class SetCommunityBan:
    def __init__(
        self,
        memberships: CommunityMembershipRepository,
        audit: AuditRecorder | None = None,
    ) -> None:
        self.memberships = memberships
        self.audit = audit

    async def execute(
        self, target_user_id: uuid.UUID, *, banned: bool, by: uuid.UUID
    ) -> CommunityMembership:
        membership = await self.memberships.get_by_user(target_user_id)
        if membership is None:
            raise ProfileNotFound("We couldn't find that community member.")
        if banned:
            membership.ban(by=by)
        else:
            membership.unban()
        if self.audit:
            await self.audit.record(
                AuditEvent(
                    action=(
                        audit_actions.COMMUNITY_MEMBER_BANNED
                        if banned
                        else audit_actions.COMMUNITY_MEMBER_UNBANNED
                    ),
                    actor_user_id=by,
                    target_type="user",
                    target_id=target_user_id,
                )
            )
        return membership


class SetProfileHidden:
    def __init__(
        self,
        profiles: CommunityProfileRepository,
        audit: AuditRecorder | None = None,
    ) -> None:
        self.profiles = profiles
        self.audit = audit

    async def execute(
        self, target_user_id: uuid.UUID, *, hidden: bool, by: uuid.UUID
    ) -> CommunityProfile:
        profile = await self.profiles.get_by_user(target_user_id)
        if profile is None:
            raise ProfileNotFound("We couldn't find that community member.")
        profile.is_hidden = hidden
        profile.touch()
        if self.audit:
            await self.audit.record(
                AuditEvent(
                    action=(
                        audit_actions.COMMUNITY_PROFILE_HIDDEN
                        if hidden
                        else audit_actions.COMMUNITY_PROFILE_UNHIDDEN
                    ),
                    actor_user_id=by,
                    target_type="user",
                    target_id=target_user_id,
                )
            )
        return profile
