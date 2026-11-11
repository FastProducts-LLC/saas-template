"""Tenant object key generation and unsafe path rejection."""

import uuid

import pytest

from app.core.storage import org_key, user_key, validate_key


def test_org_key_is_tenant_prefixed():
    org_id = uuid.uuid4()
    assert org_key(org_id, "avatars", "avatar.png") == f"org/{org_id}/avatars/avatar.png"


def test_user_key_is_user_prefixed():
    user_id = uuid.uuid4()
    assert user_key(user_id, "avatars", "avatar.png") == f"user/{user_id}/avatars/avatar.png"


@pytest.mark.parametrize("key", ["..", "../file", "org/../file", "org/files/.."])
def test_validate_key_rejects_traversal(key):
    with pytest.raises(ValueError):
        validate_key(key)


@pytest.mark.parametrize("key", ["/file", "org\\file", "\\file"])
def test_validate_key_rejects_absolute_and_backslash(key):
    with pytest.raises(ValueError):
        validate_key(key)


@pytest.mark.parametrize("key", ["", "org//file", "org/file/", "file\0.png", "a" * 513])
def test_validate_key_rejects_empty_segments_nul_and_long_keys(key):
    with pytest.raises(ValueError):
        validate_key(key)


@pytest.mark.parametrize("key", ["a" * 512, "org/avatars/a..png", "org/avatars/file.png"])
def test_validate_key_returns_valid_key_unchanged(key):
    assert validate_key(key) == key


@pytest.mark.parametrize("builder", [org_key, user_key])
@pytest.mark.parametrize("bad", ["", "..", "a/b", "/a", "a\\b", "a\0b", "a" * 513])
@pytest.mark.parametrize("field", ["area", "filename"])
def test_key_builders_validate_each_component(builder, bad, field):
    values = {"area": "avatars", "filename": "avatar.png", field: bad}
    with pytest.raises(ValueError):
        builder(uuid.uuid4(), **values)


@pytest.mark.parametrize("builder", [org_key, user_key])
def test_key_builders_validate_total_length(builder):
    with pytest.raises(ValueError):
        builder(uuid.uuid4(), "a" * 250, "b" * 250)
