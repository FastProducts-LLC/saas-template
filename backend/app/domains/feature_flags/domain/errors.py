"""Feature-flag domain errors. Every internal_code exists in shared/errors.toml."""

from app.core.exceptions import NotFoundError


class UnknownFeatureFlag(NotFoundError):
    code = "unknown_feature_flag"
    internal_code = "ERR_FLAG_001"


class FeatureDisabled(NotFoundError):
    """404, not 403 — a disabled feature is indistinguishable from a route
    that doesn't exist."""

    code = "feature_disabled"
    internal_code = "ERR_FLAG_002"
