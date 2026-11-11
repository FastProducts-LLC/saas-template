"""Auth API schemas (HTTP request/response shapes). Pydantic stays at the edge."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Generous ceiling for action-token JWTs / opaque refresh tokens (real ones
# are a few hundred bytes) — just stops multi-megabyte junk reaching crypto.
_TOKEN_MAX_LENGTH = 4096


class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(default="", max_length=60)
    email: EmailStr
    # Strength rules (length, letter/number mix, common-password blocklist)
    # are enforced in the application layer for consistent error responses.
    password: str = Field(max_length=128)
    password_confirmation: str = Field(max_length=128)
    terms_accepted: bool
    marketing_opt_in: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    # Bounded like RegisterRequest: argon2 hashes whatever it's handed, so an
    # unbounded field is a cheap CPU/memory DoS. No valid password exceeds 128.
    password: str = Field(max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(max_length=_TOKEN_MAX_LENGTH)
    password: str = Field(max_length=128)
    password_confirmation: str = Field(max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str = Field(max_length=_TOKEN_MAX_LENGTH)


class UpdateMeRequest(BaseModel):
    """Partial update — only the provided fields change."""

    first_name: str | None = Field(default=None, min_length=1, max_length=60)
    last_name: str | None = Field(default=None, max_length=60)
    marketing_opt_in: bool | None = None
    analytics_opt_out: bool | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=128)
    password: str = Field(max_length=128)
    password_confirmation: str = Field(max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    name: str  # computed full name (User.name property)
    is_superuser: bool
    marketing_opt_in: bool
    analytics_opt_out: bool
    email_verified: bool  # computed (User.email_verified property)
    created_at: datetime


class RegistrationPending(BaseModel):
    """Verify-first signup: the one register response, whether the account
    was just created or already existed. Clients show "check your email"
    and do not attempt to sign in."""

    verification_required: Literal[True] = True


class RefreshRequest(BaseModel):
    """Body-based refresh for native clients that don't hold the httpOnly cookie."""

    refresh_token: str | None = Field(default=None, max_length=_TOKEN_MAX_LENGTH)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 — OAuth2 scheme name, not a secret
    # Only populated for native clients (X-Client: mobile) — web keeps the
    # refresh token in an httpOnly cookie, out of reach of page scripts.
    refresh_token: str | None = None


class SessionResponse(TokenResponse):
    user: UserOut
