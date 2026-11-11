"""Community SQLAlchemy repositories."""

import uuid

from sqlalchemy import and_, func, literal, or_, select, tuple_
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import app.domains.community.infrastructure.orm  # noqa: F401
from app.domains.community.application.dtos import ConversationSummary
from app.domains.community.domain.entities import (
    CommunityMembership,
    CommunityProfile,
    Conversation,
    ConversationParticipant,
    MembershipTier,
    Message,
)
from app.domains.community.domain.errors import HandleTaken


def _visible():
    """Visibility rule shared by the directory and member lookups:
    profile not hidden AND membership not banned."""
    return (
        CommunityProfile.is_hidden.is_(False),
        CommunityMembership.banned_at.is_(None),
    )


class SqlAlchemyCommunityProfileRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, profile: CommunityProfile) -> None:
        self.db.add(profile)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            # Unique-handle race backstop: the use case pre-checks, the index decides.
            if "handle" in str(exc.orig):
                raise HandleTaken("Someone already uses this handle.") from exc
            raise

    async def get_by_user(self, user_id: uuid.UUID) -> CommunityProfile | None:
        return (
            await self.db.execute(
                select(CommunityProfile).where(CommunityProfile.user_id == user_id)
            )
        ).scalar_one_or_none()

    async def get_by_handle(self, handle: str) -> CommunityProfile | None:
        return (
            await self.db.execute(select(CommunityProfile).where(CommunityProfile.handle == handle))
        ).scalar_one_or_none()

    async def list_directory(
        self, *, search: str | None, limit: int, offset: int
    ) -> tuple[list[tuple[CommunityProfile, MembershipTier]], int]:
        filters = list(_visible())
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    CommunityProfile.handle.ilike(pattern),
                    CommunityProfile.display_name.ilike(pattern),
                )
            )

        join = select(CommunityProfile, CommunityMembership.tier).join(
            CommunityMembership,
            CommunityMembership.user_id == CommunityProfile.user_id,
        )
        total = (
            await self.db.execute(
                select(func.count())
                .select_from(CommunityProfile)
                .join(
                    CommunityMembership,
                    CommunityMembership.user_id == CommunityProfile.user_id,
                )
                .where(*filters)
            )
        ).scalar_one()
        rows = (
            await self.db.execute(
                join.where(*filters)
                .order_by(CommunityProfile.created_at.desc(), CommunityProfile.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return [(profile, tier) for profile, tier in rows], total

    async def list_admin(
        self, *, search: str | None, limit: int, offset: int
    ) -> tuple[list[tuple[CommunityProfile, CommunityMembership, str]], int]:
        from app.domains.auth.domain import User

        filters = []
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    CommunityProfile.handle.ilike(pattern),
                    CommunityProfile.display_name.ilike(pattern),
                    User.email.ilike(pattern),
                )
            )
        base = (
            select(CommunityProfile, CommunityMembership, User.email)
            .join(
                CommunityMembership,
                CommunityMembership.user_id == CommunityProfile.user_id,
            )
            .join(User, User.id == CommunityProfile.user_id)
        )
        total = (
            await self.db.execute(
                select(func.count())
                .select_from(CommunityProfile)
                .join(
                    CommunityMembership,
                    CommunityMembership.user_id == CommunityProfile.user_id,
                )
                .join(User, User.id == CommunityProfile.user_id)
                .where(*filters)
            )
        ).scalar_one()
        rows = (
            await self.db.execute(
                base.where(*filters)
                .order_by(CommunityProfile.created_at.desc(), CommunityProfile.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return [(p, m, email) for p, m, email in rows], total

    async def get_visible_by_handle(
        self, handle: str
    ) -> tuple[CommunityProfile, MembershipTier] | None:
        row = (
            await self.db.execute(
                select(CommunityProfile, CommunityMembership.tier)
                .join(
                    CommunityMembership,
                    CommunityMembership.user_id == CommunityProfile.user_id,
                )
                .where(CommunityProfile.handle == handle, *_visible())
            )
        ).first()
        return (row[0], row[1]) if row else None


class SqlAlchemyCommunityMembershipRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, membership: CommunityMembership) -> None:
        self.db.add(membership)
        await self.db.flush()

    async def get_by_user(self, user_id: uuid.UUID) -> CommunityMembership | None:
        return (
            await self.db.execute(
                select(CommunityMembership).where(CommunityMembership.user_id == user_id)
            )
        ).scalar_one_or_none()

    async def get_by_subscription_id(self, subscription_id: str) -> CommunityMembership | None:
        return (
            await self.db.execute(
                select(CommunityMembership).where(
                    CommunityMembership.stripe_subscription_id == subscription_id
                )
            )
        ).scalar_one_or_none()


class SqlAlchemyConversationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_dm_key(self, key: str) -> Conversation | None:
        return (
            await self.db.execute(select(Conversation).where(Conversation.dm_key == key))
        ).scalar_one_or_none()

    async def create_dm(
        self,
        *,
        dm_key: str,
        created_by: uuid.UUID,
        participant_ids: tuple[uuid.UUID, uuid.UUID],
    ) -> Conversation:
        conversation = Conversation(dm_key=dm_key, created_by=created_by)
        try:
            # Savepoint so a dm_key race doesn't poison the request transaction.
            async with self.db.begin_nested():
                self.db.add(conversation)
                await self.db.flush()
                for user_id in participant_ids:
                    self.db.add(
                        ConversationParticipant(conversation_id=conversation.id, user_id=user_id)
                    )
                await self.db.flush()
            return conversation
        except IntegrityError:
            # Racing create — the unique dm_key index collapsed us onto one
            # thread; return the winner's row.
            existing = await self.get_by_dm_key(dm_key)
            if existing is None:
                raise
            return existing

    async def get_for_participant(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[Conversation, ConversationParticipant] | None:
        row = (
            await self.db.execute(
                select(Conversation, ConversationParticipant)
                .join(
                    ConversationParticipant,
                    ConversationParticipant.conversation_id == Conversation.id,
                )
                .where(
                    Conversation.id == conversation_id,
                    ConversationParticipant.user_id == user_id,
                )
            )
        ).first()
        return (row[0], row[1]) if row else None

    async def list_for_user(self, user_id: uuid.UUID) -> list[ConversationSummary]:
        rows = (
            await self.db.execute(
                select(Conversation)
                .join(
                    ConversationParticipant,
                    ConversationParticipant.conversation_id == Conversation.id,
                )
                .where(ConversationParticipant.user_id == user_id)
                .order_by(
                    Conversation.last_message_at.desc().nulls_last(),
                    Conversation.created_at.desc(),
                )
            )
        ).scalars()
        conversations = list(rows)
        conv_ids = [c.id for c in conversations]
        if not conv_ids:
            return []

        other_rows = (
            await self.db.execute(
                select(ConversationParticipant.conversation_id, CommunityProfile)
                .join(
                    CommunityProfile,
                    CommunityProfile.user_id == ConversationParticipant.user_id,
                )
                .where(
                    ConversationParticipant.conversation_id.in_(conv_ids),
                    ConversationParticipant.user_id != user_id,
                )
            )
        ).all()
        other_by_conv = {conv_id: profile for conv_id, profile in other_rows}

        # Latest message per conversation (Postgres DISTINCT ON).
        last_rows = (
            await self.db.execute(
                select(Message)
                .ext(distinct_on(Message.conversation_id))
                .where(Message.conversation_id.in_(conv_ids))
                .order_by(
                    Message.conversation_id,
                    Message.created_at.desc(),
                    Message.id.desc(),
                )
            )
        ).scalars()
        last_by_conv = {m.conversation_id: m for m in last_rows}

        unread_rows = (
            await self.db.execute(
                select(Message.conversation_id, func.count())
                .join(
                    ConversationParticipant,
                    and_(
                        ConversationParticipant.conversation_id == Message.conversation_id,
                        ConversationParticipant.user_id == user_id,
                    ),
                )
                .where(
                    Message.conversation_id.in_(conv_ids),
                    Message.deleted_at.is_(None),
                    # sender NULL = deleted account; still unread for me.
                    or_(Message.sender_id.is_(None), Message.sender_id != user_id),
                    or_(
                        ConversationParticipant.last_read_at.is_(None),
                        Message.created_at > ConversationParticipant.last_read_at,
                    ),
                )
                .group_by(Message.conversation_id)
            )
        ).all()
        unread_by_conv = dict(unread_rows)

        return [
            ConversationSummary(
                conversation=conv,
                other=other_by_conv.get(conv.id),
                last_message=last_by_conv.get(conv.id),
                unread_count=unread_by_conv.get(conv.id, 0),
            )
            for conv in conversations
        ]


class SqlAlchemyMessageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, message: Message) -> None:
        self.db.add(message)
        await self.db.flush()

    async def get(self, message_id: uuid.UUID) -> Message | None:
        return await self.db.get(Message, message_id)

    async def list_page(
        self,
        conversation_id: uuid.UUID,
        *,
        before: Message | None,
        limit: int,
    ) -> list[Message]:
        stmt = select(Message).where(Message.conversation_id == conversation_id)
        if before is not None:
            stmt = stmt.where(
                tuple_(Message.created_at, Message.id)
                < tuple_(literal(before.created_at), literal(before.id))
            )
        stmt = stmt.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit)
        return list((await self.db.execute(stmt)).scalars())
