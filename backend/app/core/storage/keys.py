"""Validated tenant and user object keys."""

import uuid


def validate_key(key: str) -> str:
    if (
        not key
        or len(key) > 512
        or key.startswith("/")
        or "\\" in key
        or "\0" in key
        or any(segment in ("", "..") for segment in key.split("/"))
    ):
        raise ValueError("Invalid storage key")
    return key


def _segment(value: str) -> str:
    validate_key(value)
    if "/" in value:
        raise ValueError("Storage key components must not contain '/'")
    return value


def org_key(org_id: uuid.UUID, area: str, filename: str) -> str:
    return validate_key(f"org/{org_id}/{_segment(area)}/{_segment(filename)}")


def user_key(user_id: uuid.UUID, area: str, filename: str) -> str:
    return validate_key(f"user/{user_id}/{_segment(area)}/{_segment(filename)}")
