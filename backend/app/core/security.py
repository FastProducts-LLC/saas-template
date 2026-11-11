"""Password hashing (argon2), JWT access tokens, and opaque token helpers."""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from app.core.config import settings

_hasher = PasswordHasher()

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError:
        return False


# ── JWTs ─────────────────────────────────────────────────────────────
#
# Hardening beyond "one HS256 secret for everything":
#   * Key separation — each token class signs with its own key derived from
#     SECRET_KEY (HMAC-SHA256), so an action-link token can never verify as
#     an access token (or vice versa) even if a claim check were ever missed.
#   * `aud` names the exact class/purpose and is enforced by the decoder;
#     `iss` pins the deployment (FRONTEND_URL), so a token minted by staging
#     is rejected by production even when the two share a secret by mistake.
#   * `jti` gives every token a unique id for logs and audit trails.
#   * Rotation — SECRET_KEY_PREVIOUS still verifies (never signs), so the
#     secret can be rotated without invalidating in-flight tokens.

_CLASS_ACCESS = "access"
_CLASS_ACTION = "action"
_REQUIRED_CLAIMS = ["exp", "iat", "sub", "jti", "aud", "iss"]


def _derive_key(secret: str, token_class: str) -> bytes:
    return hmac.new(secret.encode(), f"jwt:{token_class}".encode(), hashlib.sha256).digest()


def _verification_keys(token_class: str) -> list[bytes]:
    secrets_ = [settings.secret_key]
    if settings.secret_key_previous:
        secrets_.append(settings.secret_key_previous)
    return [_derive_key(secret, token_class) for secret in secrets_]


def _encode(token_class: str, audience: str, payload: dict) -> str:
    claims = {**payload, "iss": settings.token_issuer, "aud": audience, "jti": uuid.uuid4().hex}
    key = _derive_key(settings.secret_key, token_class)
    return jwt.encode(claims, key, algorithm=JWT_ALGORITHM)


def _decode(token: str, token_class: str, audience: str) -> dict | None:
    for key in _verification_keys(token_class):
        try:
            return jwt.decode(
                token,
                key,
                algorithms=[JWT_ALGORITHM],
                audience=audience,
                issuer=settings.token_issuer,
                options={"require": _REQUIRED_CLAIMS},
            )
        except jwt.InvalidTokenError:
            continue
    return None


def create_access_token(user_id: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return _encode(_CLASS_ACCESS, _CLASS_ACCESS, payload)


def decode_access_claims(token: str) -> dict | None:
    """Return the full payload of a valid access token, else None. An `imp`
    claim marks an impersonation session (see create_impersonation_token)."""
    payload = _decode(token, _CLASS_ACCESS, _CLASS_ACCESS)
    if payload is None or payload.get("type") != "access":
        return None
    return payload


def decode_access_token(token: str) -> str | None:
    """Return the user id embedded in a valid access token, else None."""
    payload = decode_access_claims(token)
    return payload.get("sub") if payload else None


def create_impersonation_token(target_user_id: str, impersonator_id: str) -> str:
    """Short-lived access token for a platform admin browsing as a user.

    `type` stays "access" so the normal auth path accepts it unchanged; the
    `imp` claim records the impersonating superuser for audit/log purposes
    and lets credential-level routes refuse impersonated sessions (see
    `forbid_impersonation` in auth/interface/deps.py). No refresh token
    accompanies it, so the session ends at expiry.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": target_user_id,
        "type": "access",
        "imp": impersonator_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.impersonation_ttl_minutes),
    }
    return _encode(_CLASS_ACCESS, _CLASS_ACCESS, payload)


def create_action_token(
    user_id: str, purpose: str, ttl: timedelta, claims: dict | None = None
) -> str:
    """Short-lived, purpose-scoped JWT for email links (verify address, reset password)."""
    now = datetime.now(UTC)
    payload = {**(claims or {}), "sub": user_id, "type": purpose, "iat": now, "exp": now + ttl}
    return _encode(_CLASS_ACTION, f"{_CLASS_ACTION}:{purpose}", payload)


def decode_action_token(token: str, purpose: str) -> dict | None:
    """Return the payload of a valid action token of the given purpose, else None."""
    payload = _decode(token, _CLASS_ACTION, f"{_CLASS_ACTION}:{purpose}")
    if payload is None or payload.get("type") != purpose:
        return None
    return payload


def generate_opaque_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hash). Only the hash is ever stored."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
