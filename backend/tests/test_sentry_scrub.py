"""Sentry before_send must never ship full consumer-record payloads."""

from app.core.observability import _scrub_sentry_event


def test_scrub_redacts_request_body_and_record_shaped_extra():
    event = {
        "request": {
            "data": {"emails": ["a@b.com"], "phones": ["555"], "consumer_key": "CK"},
            "cookies": {"session": "abc"},
            "headers": {"Authorization": "Bearer x", "Content-Type": "application/json"},
            "query_string": "email=person@example.com&phone=5551234567",
        },
        "extra": {
            "record": {
                "consumer_key": "CK1",
                "emails": [{"email": "a@b.com"}],
                "phones": [{"phone": "555"}],
                "addresses": [],
            },
            "safe": "ok",
        },
    }
    scrubbed = _scrub_sentry_event(event)
    assert scrubbed["request"]["data"] == "[redacted]"
    assert scrubbed["request"]["cookies"] == "[redacted]"
    assert scrubbed["request"]["headers"]["Authorization"] == "[redacted]"
    assert "person@example.com" not in scrubbed["request"]["query_string"]
    assert scrubbed["extra"]["record"] == {"_redacted": "consumer_record"}
    assert scrubbed["extra"]["safe"] == "ok"
