"""Community application ports — interfaces consumed by use cases."""

import uuid
from typing import Protocol

from app.domains.community.application.dtos import ConversationSummary
from app.domains.community.domain.entities import (
    CommunityMembership,
    CommunityProfile,
    Conversation,
    ConversationParticipant,
    MembershipTier,
    Message,
)
from app.domains.community.domain.value_objects import CommunityPlan
from app.domains.files.domain.entities import FilePurpose, StoredFile


class CommunityProfileRepository(Protocol):
    async def add(self, profile: CommunityProfile) -> None: ...
    async def get_by_user(self, user_id: uuid.UUID) -> CommunityProfile | None: ...
    async def get_by_handle(self, handle: str) -> CommunityProfile | None: ...
    async def list_directory(
        self, *, search: str | None, limit: int, offset: int
    ) -> tuple[list[tuple[CommunityProfile, MembershipTier]], int]: ...
    async def get_visible_by_handle(
        self, handle: str
    ) -> tuple[CommunityProfile, MembershipTier] | None: ...
    async def list_admin(
        self, *, search: str | None, limit: int, offset: int
    ) -> tuple[list[tuple[CommunityProfile, CommunityMembership, str]], int]:
        """Every member incl. hidden/banned, with the account email —
        superuser moderation view only."""
        ...


class AuditRecorder(Protocol):
    """Security-event trail — satisfied structurally by the audit slice's
    recorder; writes are best-effort and never raise."""

    async def record(self, event: object) -> None: ...


class CommunityMembershipRepository(Protocol):
    async def add(self, membership: CommunityMembership) -> None: ...
    async def get_by_user(self, user_id: uuid.UUID) -> CommunityMembership | None: ...
    async def get_by_subscription_id(self, subscription_id: str) -> CommunityMembership | None: ...


class ConversationRepository(Protocol):
    async def get_by_dm_key(self, key: str) -> Conversation | None: ...

    async def create_dm(
        self,
        *,
        dm_key: str,
        created_by: uuid.UUID,
        participant_ids: tuple[uuid.UUID, uuid.UUID],
    ) -> Conversation:
        """Get-or-create semantics under races: the unique dm_key index
        decides, and the loser returns the winner's row."""
        ...

    async def get_for_participant(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[Conversation, ConversationParticipant] | None: ...

    async def list_for_user(self, user_id: uuid.UUID) -> list[ConversationSummary]: ...


class MessageRepository(Protocol):
    async def add(self, message: Message) -> None: ...
    async def get(self, message_id: uuid.UUID) -> Message | None: ...
    async def list_page(
        self,
        conversation_id: uuid.UUID,
        *,
        before: Message | None,
        limit: int,
    ) -> list[Message]: ...


class CommunityPaymentGateway(Protocol):
    """The slice of the payment provider community checkout needs —
    satisfied structurally by billing's StripeGateway (cross-slice port
    idiom, same as generations' CreditService)."""

    def is_configured(self) -> bool: ...

    def is_community_plan_purchasable(self, plan: CommunityPlan) -> bool: ...

    async def create_customer_for_user(self, *, email: str, name: str, user_id: str) -> str: ...

    async def create_community_subscription_checkout_url(
        self, *, customer_id: str, plan: CommunityPlan, user_id: str
    ) -> str: ...

    async def create_portal_url(self, *, customer_id: str) -> str: ...


class ActivityTracker(Protocol):
    """Product-analytics server events — satisfied structurally by the
    analytics slice's CaptureServerEvent (cross-slice port idiom). Writes are
    best-effort, never raise, and skip silently when `user_id` is None or the
    user opted out. Event names come from shared/events.toml."""

    async def capture_server_event(
        self, user_id: "uuid.UUID | None", event: str, properties: dict | None = None
    ) -> object: ...


class FileService(Protocol):
    """Uploaded avatars, satisfied structurally by files' public facade."""

    async def get_ready_file(self, file_id: uuid.UUID) -> StoredFile | None: ...
    def content_url(self, file: StoredFile) -> str: ...
    def file_id_from_url(self, url: str) -> uuid.UUID | None: ...
    async def delete_file(self, file_id: uuid.UUID) -> None: ...

    async def delete_owner_files(
        self, user_id: uuid.UUID, purpose: FilePurpose, *, keep: uuid.UUID | None
    ) -> int: ...
