"""Privacy-request use cases.

Fulfillment model:
  1. Verify identity (ops).
  2. Optionally mark forwarded to an upstream data processor (ops records
     the ticket/ref).
  3. Mark fulfilled with a note documenting what was done.
  4. Close when done (or reject with reason).
"""

import logging
import uuid
from datetime import UTC, datetime

from app.domains.privacy_requests.application.ports import PrivacyRequestRepository
from app.domains.privacy_requests.domain import (
    PrivacyRequest,
    PrivacyRequestIncomplete,
    PrivacyRequestInvalidTransition,
    PrivacyRequestNotFound,
    PrivacyRequestStatus,
    PrivacyRequestType,
)
from app.domains.privacy_requests.domain.entities import (
    normalize_email,
    normalize_phone,
)

logger = logging.getLogger(__name__)

# Statuses from which an admin may still act.
_OPEN = {
    PrivacyRequestStatus.RECEIVED,
    PrivacyRequestStatus.VERIFIED,
    PrivacyRequestStatus.FORWARDED,
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _require(requests: PrivacyRequestRepository, request_id: uuid.UUID) -> PrivacyRequest:
    req = await requests.get(request_id)
    if req is None:
        raise PrivacyRequestNotFound("Privacy request not found.")
    return req


class SubmitPrivacyRequest:
    """Public intake — creates a received ticket with hashed identifiers."""

    def __init__(self, requests: PrivacyRequestRepository) -> None:
        self.requests = requests

    async def execute(
        self,
        *,
        request_type: PrivacyRequestType,
        requester_email: str,
        requester_name: str | None = None,
        subject_email: str | None = None,
        subject_phone: str | None = None,
        subject_consumer_key: str | None = None,
        subject_first_name: str | None = None,
        subject_last_name: str | None = None,
        notes: str | None = None,
        ip_address: str | None = None,
    ) -> PrivacyRequest:
        email = normalize_email(requester_email)
        if not email:
            raise PrivacyRequestIncomplete("A contact email is required.")

        subj_email = normalize_email(subject_email) or email
        subj_phone = normalize_phone(subject_phone)
        key = (subject_consumer_key or "").strip() or None

        if not (subj_email or subj_phone or key):
            raise PrivacyRequestIncomplete(
                "Provide an email, phone number, or consumer key for the subject."
            )

        payload: dict = {}
        if notes:
            # Cap free-text so intake cannot become an unbounded PII store.
            payload["notes"] = notes.strip()[:2000]

        req = PrivacyRequest(
            request_type=request_type,
            status=PrivacyRequestStatus.RECEIVED,
            requester_email=email,
            requester_name=(requester_name or "").strip() or None,
            subject_email=subj_email,
            subject_phone=subj_phone,
            subject_consumer_key=key,
            subject_first_name=(subject_first_name or "").strip() or None,
            subject_last_name=(subject_last_name or "").strip() or None,
            request_payload=payload,
            ip_address=ip_address,
            deadline_at=PrivacyRequest.default_deadline(),
        )
        req.stamp_identifier_hashes()
        await self.requests.add(req)
        # Log only the opaque id + type — never subject locators.
        logger.info(
            "privacy_request.received id=%s type=%s",
            req.id,
            req.request_type.value,
        )
        return req


class VerifyPrivacyRequest:
    def __init__(self, requests: PrivacyRequestRepository) -> None:
        self.requests = requests

    async def execute(self, request_id: uuid.UUID, *, actor_user_id: uuid.UUID) -> PrivacyRequest:
        req = await _require(self.requests, request_id)
        if req.status != PrivacyRequestStatus.RECEIVED:
            raise PrivacyRequestInvalidTransition(
                f"Cannot verify a request in status {req.status.value}."
            )
        req.status = PrivacyRequestStatus.VERIFIED
        req.updated_at = _utcnow()
        req.admin_notes = _append_note(
            req.admin_notes, f"Verified by admin {actor_user_id} at {req.updated_at.isoformat()}"
        )
        return req


class ForwardPrivacyRequest:
    """Record that the request was escalated to the data provider."""

    def __init__(self, requests: PrivacyRequestRepository) -> None:
        self.requests = requests

    async def execute(
        self,
        request_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        provider_reference: str,
        notes: str | None = None,
    ) -> PrivacyRequest:
        req = await _require(self.requests, request_id)
        if req.status not in _OPEN and req.status != PrivacyRequestStatus.FULFILLED:
            raise PrivacyRequestInvalidTransition(
                f"Cannot forward a request in status {req.status.value}."
            )
        ref = provider_reference.strip()
        if not ref:
            raise PrivacyRequestIncomplete("A provider reference / ticket id is required.")

        now = _utcnow()
        req.provider_reference = ref[:128]
        req.provider_forwarded_at = now
        req.status = PrivacyRequestStatus.FORWARDED
        req.updated_at = now
        note_bits = [f"Forwarded to provider ref={ref} by admin {actor_user_id}"]
        if notes:
            note_bits.append(notes.strip()[:1000])
        req.admin_notes = _append_note(req.admin_notes, " — ".join(note_bits))
        logger.info(
            "privacy_request.forwarded id=%s provider_ref_set=%s",
            req.id,
            bool(ref),
        )
        return req


class FulfillPrivacyRequest:
    """Mark the request fulfilled (+ optional provider forward).

    What "fulfilled" means is product-specific — export the subject's data,
    delete their rows, etc. The admin documents what was done in the note;
    upstream-processor erasure is ops-tracked via ForwardPrivacyRequest.
    """

    def __init__(self, requests: PrivacyRequestRepository) -> None:
        self.requests = requests

    async def execute(
        self,
        request_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        provider_reference: str | None = None,
        notes: str | None = None,
        also_forward: bool = True,
    ) -> PrivacyRequest:
        req = await _require(self.requests, request_id)
        if req.status not in _OPEN:
            raise PrivacyRequestInvalidTransition(
                f"Cannot fulfill a request in status {req.status.value}."
            )
        # Retention purge may have wiped the subject identifiers of a stale
        # open ticket. A request whose subject can no longer be determined
        # must not be marked fulfilled — force re-collection instead.
        if req.payload_purged_at is not None and not (
            req.subject_email or req.subject_phone or req.subject_consumer_key
        ):
            raise PrivacyRequestIncomplete(
                "Raw subject identifiers were purged; the subject can no longer "
                "be identified. Re-open with fresh identifiers before fulfilling."
            )

        now = _utcnow()
        req.fulfilled_at = now
        req.fulfilled_by_user_id = actor_user_id
        req.updated_at = now

        if also_forward and provider_reference and provider_reference.strip():
            req.provider_reference = provider_reference.strip()[:128]
            req.provider_forwarded_at = now
            req.status = PrivacyRequestStatus.FORWARDED
        else:
            req.status = PrivacyRequestStatus.FULFILLED

        note_bits = [f"Fulfilled ({req.request_type.value}) by admin {actor_user_id}"]
        if notes:
            note_bits.append(notes.strip()[:1000])
        req.admin_notes = _append_note(req.admin_notes, " — ".join(note_bits))

        logger.info(
            "privacy_request.fulfilled id=%s type=%s",
            req.id,
            req.request_type.value,
        )
        return req


class ClosePrivacyRequest:
    def __init__(self, requests: PrivacyRequestRepository) -> None:
        self.requests = requests

    async def execute(
        self,
        request_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        notes: str | None = None,
    ) -> PrivacyRequest:
        req = await _require(self.requests, request_id)
        if req.status not in {
            PrivacyRequestStatus.FULFILLED,
            PrivacyRequestStatus.FORWARDED,
            PrivacyRequestStatus.REJECTED,
        }:
            raise PrivacyRequestInvalidTransition(
                "Close after fulfill/forward/reject — or reject first."
            )
        req.status = PrivacyRequestStatus.CLOSED
        req.updated_at = _utcnow()
        note = f"Closed by admin {actor_user_id}"
        if notes:
            note = f"{note} — {notes.strip()[:1000]}"
        req.admin_notes = _append_note(req.admin_notes, note)
        return req


class RejectPrivacyRequest:
    def __init__(self, requests: PrivacyRequestRepository) -> None:
        self.requests = requests

    async def execute(
        self,
        request_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        reason: str,
    ) -> PrivacyRequest:
        req = await _require(self.requests, request_id)
        if req.status not in _OPEN:
            raise PrivacyRequestInvalidTransition(
                f"Cannot reject a request in status {req.status.value}."
            )
        reason = reason.strip()
        if not reason:
            raise PrivacyRequestIncomplete("A rejection reason is required.")
        req.status = PrivacyRequestStatus.REJECTED
        req.rejection_reason = reason[:1000]
        req.updated_at = _utcnow()
        req.admin_notes = _append_note(
            req.admin_notes, f"Rejected by admin {actor_user_id}: {reason[:1000]}"
        )
        return req


class PurgePrivacyRequestPayloads:
    """Retention: drop raw intake PII; keep audit metadata + hashes."""

    def __init__(self, requests: PrivacyRequestRepository) -> None:
        self.requests = requests

    async def execute(self, older_than: datetime) -> int:
        candidates = await self.requests.list_payload_purge_candidates(older_than)
        purged = 0
        for req in candidates:
            if req.purge_raw_payload():
                purged += 1
        if purged:
            logger.info("privacy_request.payload_purge count=%s", purged)
        return purged


def _append_note(existing: str | None, addition: str) -> str:
    if not existing:
        return addition
    # Bound growth of the notes column.
    combined = f"{existing}\n{addition}"
    return combined[-8000:]
