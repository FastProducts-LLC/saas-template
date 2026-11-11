"""Plan defaults, override precedence, and entitlement boundaries."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.domains.billing.domain import Plan
from app.domains.entitlements.domain import (
    PLAN_ENTITLEMENTS,
    EntitlementKey,
    EntitlementOverride,
    is_included,
    resolve_limit,
    within_limit,
)

NOW = datetime(2026, 11, 9, tzinfo=UTC)


def override(limit_value, *, expires_at=None):
    return EntitlementOverride(
        organization_id=uuid.uuid4(),
        key=EntitlementKey.SEATS,
        limit_value=limit_value,
        expires_at=expires_at,
    )


def test_plan_defaults_cover_every_plan_and_key():
    assert set(PLAN_ENTITLEMENTS) == set(Plan)
    for defaults in PLAN_ENTITLEMENTS.values():
        assert set(defaults) == set(EntitlementKey)
    assert PLAN_ENTITLEMENTS == {
        Plan.FREE: {EntitlementKey.SEATS: 5, EntitlementKey.API_KEYS: 5},
        Plan.PRO: {EntitlementKey.SEATS: 15, EntitlementKey.API_KEYS: 20},
        Plan.TEAM: {EntitlementKey.SEATS: None, EntitlementKey.API_KEYS: 50},
    }


@pytest.mark.parametrize("plan", list(Plan))
@pytest.mark.parametrize("key", list(EntitlementKey))
def test_resolve_uses_plan_default_without_override(plan, key):
    assert resolve_limit(plan, key, None, now=NOW) == PLAN_ENTITLEMENTS[plan][key]


@pytest.mark.parametrize("limit", [None, 0, 30])
@pytest.mark.parametrize("expires_at", [None, NOW + timedelta(microseconds=1)])
def test_resolve_prefers_unexpired_override(limit, expires_at):
    custom = override(limit, expires_at=expires_at)
    assert custom.is_active(NOW)
    assert resolve_limit(Plan.PRO, EntitlementKey.SEATS, custom, now=NOW) == limit


@pytest.mark.parametrize("expires_at", [NOW, NOW - timedelta(microseconds=1)])
def test_resolve_ignores_expired_override(expires_at):
    custom = override(None, expires_at=expires_at)
    assert not custom.is_active(NOW)
    assert resolve_limit(Plan.PRO, EntitlementKey.SEATS, custom, now=NOW) == 15


def test_limit_none_means_unlimited():
    assert is_included(None)
    assert within_limit(None, 1_000_000)


def test_limit_zero_means_not_included():
    assert not is_included(0)
    assert not within_limit(0, 0)


def test_within_limit_boundary():
    assert is_included(5)
    assert within_limit(5, 4)
    assert not within_limit(5, 5)
    assert not within_limit(5, 6)
