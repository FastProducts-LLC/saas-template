"""Community persistence mapping — tables + imperative mapping.

All five tables land in one migration so the messaging schema is locked
alongside profiles, even though messaging endpoints ship in a later phase.
"""

import sqlalchemy as sa

from app.core.database import Base
from app.domains.community.domain.entities import (
    CommunityMembership,
    CommunityProfile,
    Conversation,
    ConversationParticipant,
    ConversationType,
    MembershipTier,
    Message,
    SubscriptionStatus,
)


def _str_enum(enum_cls, *, length: int):
    return sa.Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
    )


community_profiles_table = sa.Table(
    "community_profiles",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "user_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    ),
    sa.Column("handle", sa.String(30), nullable=False, unique=True, index=True),
    sa.Column("display_name", sa.String(80), nullable=False),
    sa.Column("bio", sa.String(1000), nullable=True),
    sa.Column("avatar_url", sa.String(500), nullable=True),
    sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        index=True,  # directory ordering
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
)

community_memberships_table = sa.Table(
    "community_memberships",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "user_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    ),
    sa.Column("tier", _str_enum(MembershipTier, length=16), nullable=False),
    sa.Column(
        "subscription_status",
        _str_enum(SubscriptionStatus, length=16),
        nullable=False,
    ),
    sa.Column("stripe_customer_id", sa.String(255), nullable=True, index=True),
    # Webhook lookup path: customer.subscription.* events resolve by this.
    sa.Column("stripe_subscription_id", sa.String(255), nullable=True, unique=True, index=True),
    sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
    sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "banned_by",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
)

community_conversations_table = sa.Table(
    "community_conversations",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("type", _str_enum(ConversationType, length=16), nullable=False),
    # Canonical "{min_user_id}:{max_user_id}" for DMs; NULL for future group
    # conversations. Unique so racing creates collapse to one thread.
    sa.Column("dm_key", sa.String(80), nullable=True, unique=True),
    sa.Column(
        "created_by",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True, index=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
)

community_conversation_participants_table = sa.Table(
    "community_conversation_participants",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "conversation_id",
        sa.Uuid(),
        sa.ForeignKey("community_conversations.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "user_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint("conversation_id", "user_id", name="uq_community_participant"),
    sa.Index("ix_community_participants_user_conv", "user_id", "conversation_id"),
)

community_messages_table = sa.Table(
    "community_messages",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "conversation_id",
        sa.Uuid(),
        sa.ForeignKey("community_conversations.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "sender_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("body", sa.Text(), nullable=False),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    # Hot path: keyset pagination and unread counts per conversation.
    sa.Index("ix_community_messages_conv_created", "conversation_id", "created_at", "id"),
)

Base.registry.map_imperatively(CommunityProfile, community_profiles_table)
Base.registry.map_imperatively(CommunityMembership, community_memberships_table)
Base.registry.map_imperatively(Conversation, community_conversations_table)
Base.registry.map_imperatively(ConversationParticipant, community_conversation_participants_table)
Base.registry.map_imperatively(Message, community_messages_table)
