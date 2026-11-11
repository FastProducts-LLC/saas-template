"""Community policy helpers — pure functions."""

import re
import uuid

# Mirrored by the HANDLE_PATTERN the interface schemas enforce; max length
# comes from shared/policy.toml [field_limits].community_handle.
HANDLE_RE = re.compile(r"^[a-z0-9_]{3,30}$")


def normalize_handle(raw: str) -> str:
    """Lowercase and trim; returns "" when the result isn't a valid handle."""
    handle = raw.strip().lower()
    return handle if HANDLE_RE.fullmatch(handle) else ""


def dm_key(a: uuid.UUID, b: uuid.UUID) -> str:
    """Canonical pair key: same value for (a, b) and (b, a). The unique
    index on it makes racing conversation creates collapse to one row."""
    lo, hi = sorted((str(a), str(b)))
    return f"{lo}:{hi}"
