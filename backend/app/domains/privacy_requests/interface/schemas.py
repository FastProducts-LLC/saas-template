"""Privacy-request HTTP schemas — Pydantic at the edge only.

Admin list/detail responses omit raw request_payload after purge.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.policy import PRIVACY_REQUEST_NOTES_MAX_LENGTH
from app.domains.privacy_requests.domain import PrivacyRequest

RequestType = Literal["access", "delete", "suppress"]
RequestStatus = Literal["received", "verified", "forwarded", "fulfilled", "closed", "rejected"]


class PrivacyRequestSubmitIn(BaseModel):
    request_type: RequestType
    requester_email: EmailStr
    requester_name: str | None = Field(default=None, max_length=255)
    subject_email: EmailStr | None = None
    subject_phone: str | None = Field(default=None, max_length=32)
    subject_consumer_key: str | None = Field(default=None, max_length=64)
    subject_first_name: str | None = Field(default=None, max_length=128)
    subject_last_name: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=PRIVACY_REQUEST_NOTES_MAX_LENGTH)


class PrivacyRequestSubmitOut(BaseModel):
    id: uuid.UUID
    request_type: RequestType
    status: RequestStatus
    deadline_at: datetime | None
    message: str = (
        "We received your request. We may contact you to verify your identity before fulfilling it."
    )


class PrivacyRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_type: RequestType
    status: RequestStatus
    requester_email: str | None = None
    requester_name: str | None = None
    subject_email: str | None = None
    subject_phone: str | None = None
    subject_consumer_key: str | None = None
    subject_first_name: str | None = None
    subject_last_name: str | None = None
    # Present only while payload retention window is open.
    request_payload: dict | None = None
    subject_email_hash: str | None = None
    subject_phone_hash: str | None = None
    subject_consumer_key_hash: str | None = None
    admin_notes: str | None = None
    provider_reference: str | None = None
    provider_forwarded_at: datetime | None = None
    fulfilled_at: datetime | None = None
    fulfilled_by_user_id: uuid.UUID | None = None
    rejection_reason: str | None = None
    payload_purged_at: datetime | None = None
    deadline_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, req: PrivacyRequest) -> "PrivacyRequestOut":
        payload = None if req.payload_purged_at else (req.request_payload or {})
        return cls(
            id=req.id,
            request_type=req.request_type.value,  # type: ignore[arg-type]
            status=req.status.value,  # type: ignore[arg-type]
            requester_email=req.requester_email,
            requester_name=req.requester_name,
            subject_email=req.subject_email,
            subject_phone=req.subject_phone,
            subject_consumer_key=req.subject_consumer_key,
            subject_first_name=req.subject_first_name,
            subject_last_name=req.subject_last_name,
            request_payload=payload,
            subject_email_hash=req.subject_email_hash,
            subject_phone_hash=req.subject_phone_hash,
            subject_consumer_key_hash=req.subject_consumer_key_hash,
            admin_notes=req.admin_notes,
            provider_reference=req.provider_reference,
            provider_forwarded_at=req.provider_forwarded_at,
            fulfilled_at=req.fulfilled_at,
            fulfilled_by_user_id=req.fulfilled_by_user_id,
            rejection_reason=req.rejection_reason,
            payload_purged_at=req.payload_purged_at,
            deadline_at=req.deadline_at,
            created_at=req.created_at,
            updated_at=req.updated_at,
        )


class PrivacyRequestPage(BaseModel):
    items: list[PrivacyRequestOut]
    total: int
    page: int
    page_size: int


class ForwardIn(BaseModel):
    provider_reference: str = Field(min_length=1, max_length=128)
    notes: str | None = Field(default=None, max_length=1000)


class FulfillIn(BaseModel):
    provider_reference: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=1000)
    also_forward: bool = True


class CloseIn(BaseModel):
    notes: str | None = Field(default=None, max_length=1000)


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
