"""LLM domain errors."""

from app.core.exceptions import ConflictError, NotFoundError


class LlmProviderNotConfigured(ConflictError):
    code = "llm_provider_not_configured"
    internal_code = "ERR_LLM_001"


class LlmCallFailed(ConflictError):
    code = "llm_call_failed"
    internal_code = "ERR_LLM_002"


class LlmCallNotFound(NotFoundError):
    code = "llm_call_not_found"
    internal_code = "ERR_LLM_003"
