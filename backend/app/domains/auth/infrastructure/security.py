"""Auth security adapters: argon2 hashing and JWT/opaque token services.

Thin classes over `app.core.security` so the application layer depends on
the `PasswordHasher` / `TokenService` ports, not on argon2/PyJWT/settings.
"""

from app.core import security


class Argon2PasswordHasher:
    def hash(self, password: str) -> str:
        return security.hash_password(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return security.verify_password(password, password_hash)


class JwtTokenService:
    def create_access_token(self, user_id: str) -> str:
        return security.create_access_token(user_id)

    def create_impersonation_token(self, target_user_id: str, impersonator_id: str) -> str:
        return security.create_impersonation_token(target_user_id, impersonator_id)

    def new_opaque_token(self) -> tuple[str, str]:
        return security.generate_opaque_token()

    def hash_token(self, raw: str) -> str:
        return security.hash_token(raw)

    def decode_action_token(self, token: str, purpose: str) -> dict | None:
        return security.decode_action_token(token, purpose)
