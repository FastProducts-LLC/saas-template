"""Organizations API schemas."""

import unicodedata
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from app.core.policy import ORG_INTENDED_USE_MAX_LENGTH, ORG_NAME_MAX_LENGTH
from app.domains.organizations.domain import Role


def _single_line(value: str) -> str:
    """Org names are rendered on one line everywhere — including email
    subjects, where a CR/LF makes the mail library refuse the message (the
    invitation would silently never arrive). Reject control characters and
    Unicode line/paragraph separators instead of guessing what was meant."""
    value = value.strip()
    if not value:
        raise ValueError("Name cannot be blank.")
    if any(unicodedata.category(ch) in ("Cc", "Zl", "Zp") for ch in value):
        raise ValueError("Name cannot contain line breaks or control characters.")
    return value


OrgName = Annotated[
    str, Field(min_length=1, max_length=ORG_NAME_MAX_LENGTH), AfterValidator(_single_line)
]


class OrgCreate(BaseModel):
    name: OrgName
    intended_use: str = Field(min_length=1, max_length=ORG_INTENDED_USE_MAX_LENGTH)


class OrgUpdate(BaseModel):
    name: OrgName


class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    email_domain: str | None = None
    created_at: datetime


class OrgDomainUpdate(BaseModel):
    """domain=null releases the claim."""

    domain: str | None = Field(default=None, min_length=4, max_length=253)


class OrgWithRole(OrgOut):
    role: Role


class MemberOut(BaseModel):
    id: uuid.UUID  # membership id
    user_id: uuid.UUID
    email: str
    name: str
    role: Role
    created_at: datetime


class RoleUpdate(BaseModel):
    role: Role


class InviteCreate(BaseModel):
    email: EmailStr
    role: Role = Role.MEMBER


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: Role
    expires_at: datetime
    created_at: datetime


class AcceptInviteRequest(BaseModel):
    token: str
