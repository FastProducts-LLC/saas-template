"""Property sanitization — the privacy floor, enforced in code.

Properties are identifiers, enums, and numbers. The caps below are a
backstop against a careless call site, not permission to send content:
never put prompts, message text, emails, or tokens in an event.
"""

import math
import re

MAX_PROPERTY_KEYS = 25  # GA4's per-event param limit — one cap everywhere
MAX_STRING_CHARS = 100
MAX_BODY_BYTES = 8 * 1024
INGEST_EVENTS_PER_MINUTE = 60

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


def sanitize_properties(raw: object) -> dict | None:
    """Keep valid scalar properties, drop invalid ones individually.

    Returns None only when the root is not an object (the whole event is then
    dropped); a missing/None root is an empty property bag.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        return None
    out: dict = {}
    for key, value in raw.items():
        if len(out) >= MAX_PROPERTY_KEYS:
            break
        if not isinstance(key, str) or not _KEY_RE.match(key):
            continue
        if isinstance(value, str):
            out[key] = value[:MAX_STRING_CHARS]
        elif isinstance(value, bool) or value is None:
            out[key] = value
        elif isinstance(value, int):
            out[key] = value
        elif isinstance(value, float):
            if math.isfinite(value):  # NaN/Infinity are not valid JSONB
                out[key] = value
        # lists / nested objects: dropped — scalars only
    return out
