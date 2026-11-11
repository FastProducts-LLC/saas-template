"""Community member endpoints.

Every route requires an authenticated user AND the `community` feature flag —
with the flag off the whole module 404s (ERR_FLAG_002) as if it didn't exist.
Anything that publishes content (joining, editing a profile, starting a
conversation, sending a message) additionally requires a verified email
(`CurrentVerifiedUser`, honoring EMAIL_VERIFICATION_GATE) so throwaway
sign-ups can't fill the directory or inboxes with spam; reads stay open.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.core.policy import (
    ADMIN_PAGE_SIZE,
    COMMUNITY_DIRECTORY_PAGE_SIZE,
    COMMUNITY_MESSAGES_PAGE_SIZE,
    RATE_LIMIT_COMMUNITY_SEND_MESSAGE,
    RATE_LIMIT_COMMUNITY_START_CONVERSATION,
)
from app.core.ratelimit import limiter
from app.domains.admin.interface.deps import CurrentSuperuser
from app.domains.auth.interface.deps import CurrentUser, CurrentVerifiedUser
from app.domains.billing.infrastructure.stripe_gateway import StripeGateway
from app.domains.billing.interface.deps import get_payment_gateway
from app.domains.community.application import use_cases as uc
from app.domains.community.domain.value_objects import COMMUNITY_PLANS, CommunityPlan
from app.domains.community.interface.deps import (
    get_create_community_checkout,
    get_create_community_portal,
    get_get_member_by_handle,
    get_join_community,
    get_list_community_members_admin,
    get_list_conversations,
    get_list_directory,
    get_list_messages,
    get_mark_conversation_read,
    get_my_community_state,
    get_send_message,
    get_set_community_ban,
    get_set_profile_hidden,
    get_start_conversation,
    get_update_my_avatar,
    get_update_my_profile,
)
from app.domains.community.interface.schemas import (
    AdminCommunityMemberOut,
    AdminCommunityMemberPage,
    AvatarUpdate,
    ConversationOut,
    DirectoryPage,
    MemberOut,
    MembershipCheckoutRequest,
    MembershipOut,
    MessageCreate,
    MessageOut,
    MessagePage,
    MyCommunityOut,
    PlanOut,
    ProfileCreate,
    ProfileOut,
    ProfileUpdate,
    RedirectOut,
    StartConversationRequest,
)
from app.domains.feature_flags.interface.deps import require_feature

community_router = APIRouter(
    prefix="/community",
    tags=["community"],
    dependencies=[require_feature("community")],
)

# Superuser moderation — deliberately NOT behind the feature flag, so a
# disabled community can still be moderated/inspected.
admin_router = APIRouter(prefix="/admin/community", tags=["admin-community"])

PageParam = Annotated[int, Query(ge=1)]
PageSizeParam = Annotated[int, Query(ge=1, le=100)]
SearchParam = Annotated[str | None, Query(max_length=100)]


@community_router.get("/me", response_model=MyCommunityOut)
async def get_my_community(
    user: CurrentUser,
    use_case: Annotated[uc.GetMyCommunityState, Depends(get_my_community_state)],
):
    profile, membership = await use_case.execute(user.id)
    return MyCommunityOut(
        profile=ProfileOut.from_entity(profile) if profile else None,
        membership=MembershipOut.from_entity(membership) if membership else None,
    )


@community_router.post(
    "/profile", response_model=MyCommunityOut, status_code=status.HTTP_201_CREATED
)
async def join_community(
    body: ProfileCreate,
    user: CurrentVerifiedUser,
    use_case: Annotated[uc.JoinCommunity, Depends(get_join_community)],
):
    profile, membership = await use_case.execute(
        user.id,
        handle=body.handle,
        display_name=body.display_name,
        bio=body.bio,
        avatar_url=body.avatar_url,
    )
    return MyCommunityOut(
        profile=ProfileOut.from_entity(profile),
        membership=MembershipOut.from_entity(membership),
    )


@community_router.patch("/profile", response_model=ProfileOut)
async def update_my_profile(
    body: ProfileUpdate,
    user: CurrentVerifiedUser,
    use_case: Annotated[uc.UpdateMyProfile, Depends(get_update_my_profile)],
):
    profile = await use_case.execute(user.id, updates=body.model_dump(exclude_unset=True))
    return ProfileOut.from_entity(profile)


@community_router.put("/profile/avatar", response_model=ProfileOut)
async def set_my_avatar(
    body: AvatarUpdate,
    user: CurrentVerifiedUser,
    use_case: Annotated[uc.UpdateMyAvatar, Depends(get_update_my_avatar)],
):
    return ProfileOut.from_entity(await use_case.execute(user.id, body.file_id))


@community_router.delete("/profile/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_avatar(
    user: CurrentVerifiedUser,
    use_case: Annotated[uc.UpdateMyAvatar, Depends(get_update_my_avatar)],
):
    await use_case.execute(user.id, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@community_router.get("/members", response_model=DirectoryPage)
async def list_members(
    _: CurrentUser,
    use_case: Annotated[uc.ListDirectory, Depends(get_list_directory)],
    search: SearchParam = None,
    page: PageParam = 1,
    page_size: PageSizeParam = COMMUNITY_DIRECTORY_PAGE_SIZE,
):
    items, total = await use_case.execute(
        search=search, limit=page_size, offset=(page - 1) * page_size
    )
    return DirectoryPage(
        items=[MemberOut.from_row(profile, tier) for profile, tier in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@community_router.get("/members/{handle}", response_model=MemberOut)
async def get_member(
    handle: str,
    _: CurrentUser,
    use_case: Annotated[uc.GetMemberByHandle, Depends(get_get_member_by_handle)],
):
    profile, tier = await use_case.execute(handle)
    return MemberOut.from_row(profile, tier)


@community_router.get("/plans", response_model=list[PlanOut])
async def list_plans(
    _: CurrentUser,
    gateway: Annotated[StripeGateway, Depends(get_payment_gateway)],
):
    return [
        PlanOut(
            plan=spec.plan.value,  # type: ignore[arg-type]
            name=spec.name,
            price_cents=spec.price_cents,
            interval=spec.interval,
            purchasable=gateway.is_configured()
            and gateway.is_community_plan_purchasable(spec.plan),
        )
        for spec in COMMUNITY_PLANS.values()
    ]


@community_router.post("/membership/checkout", response_model=RedirectOut)
async def create_membership_checkout(
    body: MembershipCheckoutRequest,
    user: CurrentVerifiedUser,
    use_case: Annotated[uc.CreateCommunityCheckout, Depends(get_create_community_checkout)],
):
    url = await use_case.execute(user, CommunityPlan(body.plan))
    return RedirectOut(url=url)


@community_router.post("/membership/portal", response_model=RedirectOut)
async def create_membership_portal(
    user: CurrentVerifiedUser,
    use_case: Annotated[uc.CreateCommunityPortal, Depends(get_create_community_portal)],
):
    url = await use_case.execute(user.id)
    return RedirectOut(url=url)


@community_router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    user: CurrentUser,
    use_case: Annotated[uc.ListConversations, Depends(get_list_conversations)],
):
    summaries = await use_case.execute(user.id)
    return [ConversationOut.from_summary(s) for s in summaries]


@community_router.post(
    "/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED
)
@limiter.limit(RATE_LIMIT_COMMUNITY_START_CONVERSATION)
async def start_conversation(
    request: Request,
    # slowapi (headers_enabled) injects X-RateLimit-* into this — a decorated
    # route without it 500s on every request in live mode.
    response: Response,
    body: StartConversationRequest,
    user: CurrentVerifiedUser,
    use_case: Annotated[uc.StartConversation, Depends(get_start_conversation)],
):
    conversation, recipient = await use_case.execute(
        user.id, recipient_handle=body.recipient_handle
    )
    return ConversationOut(
        id=conversation.id,
        other=MemberOut(
            handle=recipient.handle,
            display_name=recipient.display_name,
            bio=recipient.bio,
            avatar_url=recipient.avatar_url,
            tier="free",  # tier isn't surfaced in conversation lists
            joined_at=recipient.created_at,
        ),
        last_message_preview=None,
        last_message_at=conversation.last_message_at,
        unread_count=0,
        created_at=conversation.created_at,
    )


@community_router.get("/conversations/{conversation_id}/messages", response_model=MessagePage)
async def list_messages(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    use_case: Annotated[uc.ListMessages, Depends(get_list_messages)],
    before: Annotated[uuid.UUID | None, Query()] = None,
    page_size: Annotated[int, Query(ge=1, le=100)] = COMMUNITY_MESSAGES_PAGE_SIZE,
):
    messages = await use_case.execute(user.id, conversation_id, before_id=before, limit=page_size)
    return MessagePage(
        items=[MessageOut.from_entity(m, viewer_id=user.id) for m in messages],
        next_before=messages[-1].id if len(messages) == page_size else None,
    )


@community_router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(RATE_LIMIT_COMMUNITY_SEND_MESSAGE)
async def send_message(
    request: Request,
    # slowapi (headers_enabled) injects X-RateLimit-* into this — a decorated
    # route without it 500s on every request in live mode.
    response: Response,
    conversation_id: uuid.UUID,
    body: MessageCreate,
    user: CurrentVerifiedUser,
    use_case: Annotated[uc.SendMessage, Depends(get_send_message)],
):
    message = await use_case.execute(user.id, conversation_id, body=body.body)
    return MessageOut.from_entity(message, viewer_id=user.id)


@community_router.post(
    "/conversations/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT
)
async def mark_conversation_read(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    use_case: Annotated[uc.MarkConversationRead, Depends(get_mark_conversation_read)],
):
    await use_case.execute(user.id, conversation_id)


@admin_router.get("/members", response_model=AdminCommunityMemberPage)
async def admin_list_members(
    _: CurrentSuperuser,
    use_case: Annotated[uc.ListCommunityMembersAdmin, Depends(get_list_community_members_admin)],
    search: SearchParam = None,
    page: PageParam = 1,
    page_size: PageSizeParam = ADMIN_PAGE_SIZE,
):
    items, total = await use_case.execute(
        search=search, limit=page_size, offset=(page - 1) * page_size
    )
    return AdminCommunityMemberPage(
        items=[
            AdminCommunityMemberOut.from_row(profile, membership, email)
            for profile, membership, email in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.post("/members/{user_id}/ban", status_code=status.HTTP_204_NO_CONTENT)
async def admin_ban_member(
    user_id: uuid.UUID,
    admin: CurrentSuperuser,
    use_case: Annotated[uc.SetCommunityBan, Depends(get_set_community_ban)],
):
    await use_case.execute(user_id, banned=True, by=admin.id)


@admin_router.post("/members/{user_id}/unban", status_code=status.HTTP_204_NO_CONTENT)
async def admin_unban_member(
    user_id: uuid.UUID,
    admin: CurrentSuperuser,
    use_case: Annotated[uc.SetCommunityBan, Depends(get_set_community_ban)],
):
    await use_case.execute(user_id, banned=False, by=admin.id)


@admin_router.post("/members/{user_id}/hide-profile", status_code=status.HTTP_204_NO_CONTENT)
async def admin_hide_profile(
    user_id: uuid.UUID,
    admin: CurrentSuperuser,
    use_case: Annotated[uc.SetProfileHidden, Depends(get_set_profile_hidden)],
):
    await use_case.execute(user_id, hidden=True, by=admin.id)


@admin_router.post("/members/{user_id}/unhide-profile", status_code=status.HTTP_204_NO_CONTENT)
async def admin_unhide_profile(
    user_id: uuid.UUID,
    admin: CurrentSuperuser,
    use_case: Annotated[uc.SetProfileHidden, Depends(get_set_profile_hidden)],
):
    await use_case.execute(user_id, hidden=False, by=admin.id)
