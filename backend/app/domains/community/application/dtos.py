"""Community application DTOs."""

from dataclasses import dataclass

from app.domains.community.domain.entities import (
    CommunityProfile,
    Conversation,
    Message,
)


@dataclass(frozen=True)
class ConversationSummary:
    """One row of the conversation list: the thread, who it's with, the
    latest message, and how many are unread for the requesting user."""

    conversation: Conversation
    # None when the other account was deleted (profile CASCADEd away).
    other: CommunityProfile | None
    last_message: Message | None
    unread_count: int
