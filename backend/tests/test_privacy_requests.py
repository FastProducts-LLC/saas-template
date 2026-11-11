"""Unit + API tests for privacy request intake, fulfillment, and retention."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.domains.privacy_requests.application.use_cases import (
    FulfillPrivacyRequest,
    PurgePrivacyRequestPayloads,
    SubmitPrivacyRequest,
)
from app.domains.privacy_requests.domain import (
    PrivacyRequest,
    PrivacyRequestIncomplete,
    PrivacyRequestStatus,
    PrivacyRequestType,
)
from app.domains.privacy_requests.domain.entities import REQUEST_PAYLOAD_RETENTION_DAYS
from tests.helpers import make_superuser, register_and_login


class FakePrivacyRepo:
    def __init__(self) -> None:
        self.items: list[PrivacyRequest] = []

    async def add(self, request: PrivacyRequest) -> None:
        self.items.append(request)

    async def get(self, request_id: uuid.UUID) -> PrivacyRequest | None:
        return next((r for r in self.items if r.id == request_id), None)

    async def list_requests(self, *, status=None, limit=25, offset=0):
        rows = self.items
        if status is not None:
            rows = [r for r in rows if r.status == status]
        return rows[offset : offset + limit], len(rows)

    async def list_payload_purge_candidates(self, older_than: datetime):
        return [r for r in self.items if r.payload_purged_at is None and r.created_at < older_than]


async def test_submit_requires_contact_email():
    uc = SubmitPrivacyRequest(FakePrivacyRepo())
    with pytest.raises(PrivacyRequestIncomplete):
        await uc.execute(request_type=PrivacyRequestType.ACCESS, requester_email="")


async def test_submit_stamps_hashes_and_deadline():
    repo = FakePrivacyRepo()
    uc = SubmitPrivacyRequest(repo)
    req = await uc.execute(
        request_type=PrivacyRequestType.SUPPRESS,
        requester_email="Person@Example.COM",
        subject_phone="(555) 123-4567",
        notes="please remove me",
    )
    assert req.status == PrivacyRequestStatus.RECEIVED
    assert req.requester_email == "person@example.com"
    assert req.subject_phone == "5551234567"
    assert req.subject_email_hash
    assert req.subject_phone_hash
    assert req.deadline_at is not None
    assert req.request_payload.get("notes") == "please remove me"


async def test_fulfill_with_forward_marks_forwarded():
    requests = FakePrivacyRepo()
    submit = SubmitPrivacyRequest(requests)
    req = await submit.execute(
        request_type=PrivacyRequestType.DELETE,
        requester_email="ada@example.com",
        subject_email="ada@example.com",
    )
    actor = uuid.uuid4()
    fulfill = FulfillPrivacyRequest(requests)
    updated = await fulfill.execute(
        req.id,
        actor_user_id=actor,
        provider_reference="PROV-1",
        also_forward=True,
    )
    assert updated.status == PrivacyRequestStatus.FORWARDED
    assert updated.provider_reference == "PROV-1"
    assert updated.fulfilled_at is not None
    assert updated.fulfilled_by_user_id == actor


async def test_fulfill_without_forward_marks_fulfilled():
    requests = FakePrivacyRepo()
    submit = SubmitPrivacyRequest(requests)
    req = await submit.execute(
        request_type=PrivacyRequestType.ACCESS,
        requester_email="ada@example.com",
    )
    fulfill = FulfillPrivacyRequest(requests)
    updated = await fulfill.execute(
        req.id,
        actor_user_id=uuid.uuid4(),
        notes="data export sent",
        also_forward=False,
    )
    assert updated.status == PrivacyRequestStatus.FULFILLED
    assert "data export sent" in (updated.admin_notes or "")


async def test_fulfill_refuses_purged_request_with_no_identifiers():
    repo = FakePrivacyRepo()
    submit = SubmitPrivacyRequest(repo)
    req = await submit.execute(
        request_type=PrivacyRequestType.DELETE,
        requester_email="gone@example.com",
    )
    req.purge_raw_payload()  # retention purge wiped the subject identifiers

    with pytest.raises(PrivacyRequestIncomplete):
        await FulfillPrivacyRequest(repo).execute(req.id, actor_user_id=uuid.uuid4())
    assert req.status == PrivacyRequestStatus.RECEIVED  # untouched


async def test_purge_drops_raw_payload_keeps_hashes():
    repo = FakePrivacyRepo()
    submit = SubmitPrivacyRequest(repo)
    req = await submit.execute(
        request_type=PrivacyRequestType.ACCESS,
        requester_email="keep@example.com",
        subject_phone="5551112222",
    )
    req.created_at = datetime.now(UTC) - timedelta(days=REQUEST_PAYLOAD_RETENTION_DAYS + 1)
    purged = await PurgePrivacyRequestPayloads(repo).execute(
        datetime.now(UTC) - timedelta(days=REQUEST_PAYLOAD_RETENTION_DAYS)
    )
    assert purged == 1
    assert req.payload_purged_at is not None
    assert req.requester_email is None
    assert req.subject_phone is None
    assert req.request_payload == {}
    assert req.subject_email_hash
    assert req.subject_phone_hash
    assert req.status == PrivacyRequestStatus.RECEIVED


# ── API ───────────────────────────────────────────────────────────────


async def test_public_submit_creates_request(client):
    res = await client.post(
        "/api/privacy/requests",
        json={
            "request_type": "suppress",
            "requester_email": "consumer@example.com",
            "subject_email": "consumer@example.com",
            "notes": "Please suppress my data",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "received"
    assert body["request_type"] == "suppress"
    assert "id" in body


async def test_admin_queue_and_fulfill_flow(client, db):
    user, headers = await register_and_login(client, "priv-admin@example.com")
    await make_superuser(db, user["id"])

    create = await client.post(
        "/api/privacy/requests",
        json={
            "request_type": "access",
            "requester_email": "subject@example.com",
            "subject_phone": "5550001111",
        },
    )
    assert create.status_code == 201, create.text
    request_id = create.json()["id"]

    listed = await client.get("/api/admin/privacy-requests", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] >= 1

    verify = await client.post(f"/api/admin/privacy-requests/{request_id}/verify", headers=headers)
    assert verify.status_code == 200, verify.text
    assert verify.json()["status"] == "verified"

    fulfill = await client.post(
        f"/api/admin/privacy-requests/{request_id}/fulfill",
        headers=headers,
        json={"also_forward": False, "notes": "data export sent"},
    )
    assert fulfill.status_code == 200, fulfill.text
    assert fulfill.json()["status"] == "fulfilled"


async def test_non_superuser_cannot_list_privacy_queue(client):
    _, headers = await register_and_login(client, "normie@example.com")
    res = await client.get("/api/admin/privacy-requests", headers=headers)
    assert res.status_code == 403
