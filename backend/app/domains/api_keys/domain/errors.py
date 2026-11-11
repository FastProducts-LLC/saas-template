"""API key domain errors. Every internal_code exists in shared/errors.toml."""

from app.core.exceptions import NotFoundError


class ApiKeyNotFound(NotFoundError):
    code = "api_key_not_found"
    internal_code = "ERR_KEY_001"
