"""Generations domain errors."""

from app.core.exceptions import ConflictError, NotFoundError


class GenerationNotFound(NotFoundError):
    code = "generation_not_found"
    internal_code = "ERR_GEN_001"


class ProviderNotConfigured(ConflictError):
    code = "provider_not_configured"
    internal_code = "ERR_GEN_002"


class GenerationFailed(ConflictError):
    code = "generation_failed"
    internal_code = "ERR_GEN_003"


class ResultNotReady(ConflictError):
    code = "result_not_ready"
    internal_code = "ERR_GEN_004"


class NotCancelable(ConflictError):
    code = "generation_not_cancelable"
    internal_code = "ERR_GEN_005"


class NotDeletable(ConflictError):
    code = "generation_not_deletable"
    internal_code = "ERR_GEN_006"
