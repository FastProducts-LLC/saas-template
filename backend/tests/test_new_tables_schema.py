"""Database constraints for files, subscriptions, and entitlement overrides."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.storage import org_key, user_key
from app.domains.billing.domain import BillingInterval, Plan, PlanSubscriptionStatus, Subscription
from app.domains.billing.infrastructure.orm import subscriptions_table
from app.domains.entitlements.domain import EntitlementKey, EntitlementOverride
from app.domains.entitlements.infrastructure.orm import organization_entitlements_table
from app.domains.files.domain import FilePurpose, StoredFile, StoredFileStatus
from app.domains.files.infrastructure.orm import stored_files_table
from tests.helpers import create_org, register_and_login


async def test_stored_files_requires_an_owner(client, db):
    user, headers = await register_and_login(client)
    user_id = uuid.UUID(user["id"])
    # Core insert intentionally bypasses the domain constructor's owner guard.
    with pytest.raises(IntegrityError, match="ck_stored_files_has_owner"):
        async with db.begin_nested():
            await db.execute(
                stored_files_table.insert().values(
                    id=uuid.uuid4(),
                    organization_id=None,
                    user_id=None,
                    purpose=FilePurpose.AVATAR,
                    key=user_key(user_id, "avatars", "ownerless.png"),
                    content_type="image/png",
                    status=StoredFileStatus.PENDING,
                    created_by_id=user_id,
                )
            )

    # Both supported ownership modes can actually be persisted.
    owned = StoredFile(
        key=user_key(user_id, "avatars", "owned.png"),
        purpose=FilePurpose.AVATAR,
        content_type="image/png",
        created_by_id=user_id,
        user_id=user_id,
    )
    db.add(owned)
    await db.flush()
    await db.refresh(owned)
    assert owned.status is StoredFileStatus.PENDING
    assert owned.purpose is FilePurpose.AVATAR

    org = await create_org(client, headers)
    org_id = uuid.UUID(org["id"])
    org_owned = StoredFile(
        key=org_key(org_id, "avatars", "owned.png"),
        purpose=FilePurpose.AVATAR,
        content_type="image/png",
        created_by_id=user_id,
        organization_id=org_id,
    )
    db.add(org_owned)
    await db.flush()
    await db.refresh(org_owned)
    assert org_owned.organization_id == org_id
    assert org_owned.user_id is None


async def test_subscriptions_one_per_org(client, db):
    _, headers = await register_and_login(client)
    org = await create_org(client, headers)
    org_id = uuid.UUID(org["id"])
    first = Subscription(
        organization_id=org_id,
        stripe_subscription_id="sub_first",
        plan=Plan.PRO,
        interval=BillingInterval.MONTHLY,
        status=PlanSubscriptionStatus.ACTIVE,
    )
    db.add(first)
    await db.flush()
    await db.refresh(first)
    assert first.plan is Plan.PRO
    assert first.interval is BillingInterval.MONTHLY
    assert first.status is PlanSubscriptionStatus.ACTIVE

    with pytest.raises(IntegrityError, match="subscriptions_organization_id_key"):
        async with db.begin_nested():
            await db.execute(
                subscriptions_table.insert().values(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    stripe_subscription_id="sub_second",
                    plan=Plan.TEAM,
                    interval=BillingInterval.ANNUAL,
                    status=PlanSubscriptionStatus.ACTIVE,
                )
            )


async def test_entitlement_override_unique_per_org_and_key(client, db):
    _, headers = await register_and_login(client)
    org = await create_org(client, headers)
    org_id = uuid.UUID(org["id"])
    first = EntitlementOverride(organization_id=org_id, key=EntitlementKey.SEATS, limit_value=None)
    db.add(first)
    await db.flush()
    await db.refresh(first)
    assert first.key is EntitlementKey.SEATS
    assert first.limit_value is None

    with pytest.raises(IntegrityError, match="uq_organization_entitlements_org_key"):
        async with db.begin_nested():
            await db.execute(
                organization_entitlements_table.insert().values(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    key=EntitlementKey.SEATS,
                    limit_value=20,
                    source="admin",
                )
            )

    other_key = EntitlementOverride(
        organization_id=org_id, key=EntitlementKey.API_KEYS, limit_value=0
    )
    db.add(other_key)
    await db.flush()
    await db.refresh(other_key)
    assert other_key.limit_value == 0


def test_stored_file_constructor_requires_an_owner():
    with pytest.raises(ValueError, match="owner"):
        StoredFile(
            key="avatars/ownerless.png",
            purpose=FilePurpose.AVATAR,
            content_type="image/png",
            created_by_id=uuid.uuid4(),
        )


def test_stored_file_confirm_sets_size_status_and_timestamp():
    user_id = uuid.uuid4()
    file = StoredFile(
        key=user_key(user_id, "avatars", "avatar.png"),
        purpose=FilePurpose.AVATAR,
        content_type="image/png",
        created_by_id=user_id,
        user_id=user_id,
    )
    assert not file.is_ready
    assert file.size_bytes is None
    assert file.confirmed_at is None
    before = datetime.now(UTC)
    file.confirm(size_bytes=123)
    assert file.is_ready
    assert file.status == StoredFileStatus.READY
    assert file.size_bytes == 123
    assert before <= file.confirmed_at <= datetime.now(UTC)
