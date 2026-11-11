"""Credits domain errors."""

from app.core.exceptions import ConflictError, NotFoundError


class InsufficientCredits(ConflictError):
    code = "insufficient_credits"
    internal_code = "ERR_CRD_001"


class ReservationNotActive(ConflictError):
    code = "reservation_not_active"
    internal_code = "ERR_CRD_002"


class ReservationNotFound(NotFoundError):
    code = "reservation_not_found"
    internal_code = "ERR_CRD_003"


class UnknownAction(ConflictError):
    code = "unknown_action"
    internal_code = "ERR_CRD_004"


class UnknownCreditPack(ConflictError):
    code = "unknown_credit_pack"
    internal_code = "ERR_CRD_005"


class MemberCreditLimitExceeded(ConflictError):
    code = "member_credit_limit_exceeded"
    internal_code = "ERR_CRD_006"


class LimitTargetNotMember(NotFoundError):
    code = "limit_target_not_member"
    internal_code = "ERR_CRD_007"
