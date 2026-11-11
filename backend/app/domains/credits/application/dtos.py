"""Read-side DTOs for credit usage reporting."""

import uuid
from dataclasses import dataclass, field

from app.domains.credits.domain import CreditAction


@dataclass(frozen=True)
class UsageRow:
    """One SQL group row: (actor x action) with joined display names.

    The actor is a user (user_id/email/name), an API key (api_key_id/name),
    or all-null — usage whose user AND key were since deleted."""

    user_id: uuid.UUID | None
    user_email: str | None
    user_name: str | None
    api_key_id: uuid.UUID | None
    api_key_name: str | None
    action: CreditAction
    count: int
    credits: int


@dataclass
class UsageAction:
    action: CreditAction
    count: int
    credits: int


@dataclass
class ActorUsage:
    """Per-actor aggregate for the usage endpoint, with the action breakdown
    and (when configured) the member's monthly limit."""

    user_id: uuid.UUID | None
    user_email: str | None
    user_name: str | None
    api_key_id: uuid.UUID | None
    api_key_name: str | None
    credits: int
    count: int
    limit: int | None
    actions: list[UsageAction] = field(default_factory=list)
