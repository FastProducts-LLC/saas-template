"""Error tracking. A no-op unless SENTRY_DSN is set.

Request correlation ids, problem+json rendering, and structured error logs
live in `app.core.error_handling`; this module only ships exceptions to
Sentry. For per-code issue grouping, add a capture call in
`error_handling._record_error` with `fingerprint=[code]`.

Never send PII / privacy-request payloads to Sentry — see
`_scrub_sentry_event`.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.config import settings

# Keys / path fragments that often carry PII.
_SENSITIVE_KEY_RE = re.compile(
    r"(email|phone|password|token|secret|authorization|cookie|consumer_key|"
    r"request_payload|addresses|emails|phones|device_ids|ip_addresses|"
    r"date_of_birth|alternate_names)",
    re.I,
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_LONG_DIGIT_RE = re.compile(r"\b\d{7,}\b")


def _redact_string(value: str) -> str:
    value = _EMAIL_RE.sub("[redacted-email]", value)
    value = _LONG_DIGIT_RE.sub("[redacted-digits]", value)
    return value


def _scrub_value(value: Any, *, key: str | None = None) -> Any:
    if key and _SENSITIVE_KEY_RE.search(key):
        return "[redacted]"
    if isinstance(value, dict):
        # Drop whole consumer-record shaped blobs rather than shipping them.
        if "consumer_key" in value and (
            "emails" in value or "phones" in value or "addresses" in value
        ):
            return {"_redacted": "consumer_record"}
        if "request_payload" in value or ("subject_email" in value and "request_type" in value):
            return {"_redacted": "privacy_request"}
        return {k: _scrub_value(v, key=k) for k, v in value.items()}
    if isinstance(value, list):
        # Cap list size so a dumped record array cannot flood Sentry.
        if len(value) > 20:
            return [_scrub_value(v) for v in value[:20]] + [f"[+{len(value) - 20} more redacted]"]
        return [_scrub_value(v) for v in value]
    if isinstance(value, str):
        if len(value) > 2000:
            value = value[:2000] + "…[truncated]"
        return _redact_string(value)
    return value


def _scrub_sentry_event(
    event: dict[str, Any], _hint: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Strip PII / privacy intake from anything headed to Sentry."""
    if "request" in event and isinstance(event["request"], dict):
        req = event["request"]
        if "data" in req:
            req["data"] = "[redacted]"
        if "cookies" in req:
            req["cookies"] = "[redacted]"
        if "headers" in req and isinstance(req["headers"], dict):
            req["headers"] = {
                k: ("[redacted]" if _SENSITIVE_KEY_RE.search(k) else v)
                for k, v in req["headers"].items()
            }
        if "query_string" in req and isinstance(req["query_string"], str):
            req["query_string"] = _redact_string(req["query_string"])
    if "extra" in event:
        event["extra"] = _scrub_value(event["extra"])
    if "contexts" in event:
        event["contexts"] = _scrub_value(event["contexts"])
    if "exception" in event and isinstance(event["exception"], dict):
        values = event["exception"].get("values") or []
        for item in values:
            if isinstance(item, dict) and "value" in item and isinstance(item["value"], str):
                item["value"] = _redact_string(item["value"])[:500]
    return event


def setup_sentry() -> None:
    """Initialise Sentry error tracking. Call once at startup (app and worker)."""
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        # Performance tracing; lower in high-traffic production apps.
        traces_sample_rate=settings.sentry_traces_sample_rate,
        # PII (user ids, cookies, IPs) stays out of Sentry by default.
        send_default_pii=False,
        before_send=_scrub_sentry_event,
    )
