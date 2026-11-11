"""Privacy-request domain errors."""

from app.core.exceptions import AppError, ConflictError, NotFoundError


class PrivacyRequestNotFound(NotFoundError):
    code = "privacy_request_not_found"
    internal_code = "ERR_PRIV_001"


class PrivacyRequestInvalidTransition(ConflictError):
    code = "privacy_request_invalid_transition"
    internal_code = "ERR_PRIV_002"


class PrivacyRequestIncomplete(AppError):
    status_code = 400
    code = "privacy_request_incomplete"
    internal_code = "ERR_PRIV_003"
