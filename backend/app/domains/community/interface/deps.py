"""Community composition root — the ONLY place use cases meet concrete adapters."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.policy import COMMUNITY_PREMIUM_GRACE_DAYS
from app.domains.analytics.interface.deps import build_activity_tracker
from app.domains.audit.interface.deps import get_audit_recorder
from app.domains.billing.interface.deps import get_payment_gateway
from app.domains.community.application import use_cases as uc
from app.domains.community.application.ports import AuditRecorder
from app.domains.community.infrastructure.repositories import (
    SqlAlchemyCommunityMembershipRepository,
    SqlAlchemyCommunityProfileRepository,
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)
from app.domains.files.interface.deps import build_file_service

DB = Annotated[AsyncSession, Depends(get_db)]
Audit = Annotated[AuditRecorder, Depends(get_audit_recorder)]


def get_list_community_members_admin(db: DB) -> uc.ListCommunityMembersAdmin:
    return uc.ListCommunityMembersAdmin(SqlAlchemyCommunityProfileRepository(db))


def get_set_community_ban(db: DB, audit: Audit) -> uc.SetCommunityBan:
    return uc.SetCommunityBan(SqlAlchemyCommunityMembershipRepository(db), audit)


def get_set_profile_hidden(db: DB, audit: Audit) -> uc.SetProfileHidden:
    return uc.SetProfileHidden(SqlAlchemyCommunityProfileRepository(db), audit)


def get_join_community(db: DB) -> uc.JoinCommunity:
    return uc.JoinCommunity(
        SqlAlchemyCommunityProfileRepository(db),
        SqlAlchemyCommunityMembershipRepository(db),
    )


def get_update_my_profile(db: DB) -> uc.UpdateMyProfile:
    return uc.UpdateMyProfile(
        SqlAlchemyCommunityProfileRepository(db),
        SqlAlchemyCommunityMembershipRepository(db),
        build_file_service(db),
    )


def get_update_my_avatar(db: DB) -> uc.UpdateMyAvatar:
    return uc.UpdateMyAvatar(
        SqlAlchemyCommunityProfileRepository(db),
        SqlAlchemyCommunityMembershipRepository(db),
        build_file_service(db),
    )


def get_my_community_state(db: DB) -> uc.GetMyCommunityState:
    return uc.GetMyCommunityState(
        SqlAlchemyCommunityProfileRepository(db),
        SqlAlchemyCommunityMembershipRepository(db),
    )


def get_list_directory(db: DB) -> uc.ListDirectory:
    return uc.ListDirectory(SqlAlchemyCommunityProfileRepository(db))


def get_get_member_by_handle(db: DB) -> uc.GetMemberByHandle:
    return uc.GetMemberByHandle(SqlAlchemyCommunityProfileRepository(db))


def get_create_community_checkout(db: DB) -> uc.CreateCommunityCheckout:
    return uc.CreateCommunityCheckout(
        SqlAlchemyCommunityMembershipRepository(db),
        get_payment_gateway(),
        grace_days=COMMUNITY_PREMIUM_GRACE_DAYS,
    )


def get_create_community_portal(db: DB) -> uc.CreateCommunityPortal:
    return uc.CreateCommunityPortal(
        SqlAlchemyCommunityMembershipRepository(db), get_payment_gateway()
    )


def _gate(db: AsyncSession) -> uc._MessagingGate:
    return uc._MessagingGate(
        SqlAlchemyCommunityMembershipRepository(db),
        grace_days=COMMUNITY_PREMIUM_GRACE_DAYS,
    )


def get_start_conversation(db: DB) -> uc.StartConversation:
    return uc.StartConversation(
        SqlAlchemyCommunityProfileRepository(db),
        SqlAlchemyConversationRepository(db),
        _gate(db),
    )


def get_send_message(db: DB) -> uc.SendMessage:
    return uc.SendMessage(
        SqlAlchemyConversationRepository(db),
        SqlAlchemyMessageRepository(db),
        _gate(db),
    )


def get_list_conversations(db: DB) -> uc.ListConversations:
    return uc.ListConversations(SqlAlchemyConversationRepository(db), _gate(db))


def get_list_messages(db: DB) -> uc.ListMessages:
    return uc.ListMessages(
        SqlAlchemyConversationRepository(db),
        SqlAlchemyMessageRepository(db),
        _gate(db),
    )


def get_mark_conversation_read(db: DB) -> uc.MarkConversationRead:
    return uc.MarkConversationRead(SqlAlchemyConversationRepository(db), _gate(db))


def build_community_membership_service(
    db: AsyncSession,
) -> uc.ApplyCommunitySubscriptionEvent:
    """For billing's webhook composition root — satisfies its
    CommunityMembershipService port structurally."""
    return uc.ApplyCommunitySubscriptionEvent(
        SqlAlchemyCommunityMembershipRepository(db), build_activity_tracker(db)
    )
