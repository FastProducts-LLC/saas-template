"""Community domain errors. Every internal_code exists in shared/errors.toml."""

from app.core.exceptions import (
    AppError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)


class ProfileNotFound(NotFoundError):
    code = "community_profile_not_found"
    internal_code = "ERR_COMM_001"


class HandleTaken(ConflictError):
    code = "community_handle_taken"
    internal_code = "ERR_COMM_002"


class NotACommunityMember(PermissionDeniedError):
    code = "not_a_community_member"
    internal_code = "ERR_COMM_003"


class PremiumRequired(PermissionDeniedError):
    """The frontend routes this code to the upgrade prompt, not a toast."""

    code = "community_premium_required"
    internal_code = "ERR_COMM_004"


class CommunityBanned(PermissionDeniedError):
    code = "community_banned"
    internal_code = "ERR_COMM_005"


class ConversationNotFound(NotFoundError):
    code = "community_conversation_not_found"
    internal_code = "ERR_COMM_006"


class CannotMessageSelf(AppError):
    status_code = 400
    code = "community_cannot_message_self"
    internal_code = "ERR_COMM_007"


class AlreadyPremium(ConflictError):
    code = "community_already_premium"
    internal_code = "ERR_COMM_009"


class RecipientUnavailable(NotFoundError):
    """404 whether the recipient doesn't exist, is hidden, or is banned —
    never leaks moderation state."""

    code = "community_recipient_unavailable"
    internal_code = "ERR_COMM_008"
