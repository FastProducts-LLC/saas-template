"""Auth domain services: the password policy.

Pure functions over pure data — no I/O, no framework. The same rules are
mirrored client-side for live feedback (frontend password-policy module);
this is the authoritative check.

Per-project: change `min_length` in shared/policy.toml and run
`python3 scripts/gen_policy.py` — backend and frontend both consume the
generated constant, so they can't drift (docs/customization.md § Security).
"""

from app.core.policy import PASSWORD_MIN_LENGTH
from app.domains.auth.domain.errors import PasswordTooWeak

__all__ = ["PASSWORD_MIN_LENGTH", "validate_password_strength", "COMMON_PASSWORDS"]

# Frequently used passwords rejected at registration. Top entries from leaked
# password datasets; extend or swap for a larger list (e.g. the SecLists
# 10k-most-common file) without changing the validation logic.
COMMON_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "password123",
        "12345678",
        "123456789",
        "1234567890",
        "qwerty123",
        "qwertyuiop",
        "iloveyou1",
        "sunshine1",
        "princess1",
        "football1",
        "baseball1",
        "welcome1",
        "abc12345",
        "monkey123",
        "dragon123",
        "master123",
        "letmein1",
        "shadow123",
        "superman1",
        "michael1",
        "jennifer1",
        "computer1",
        "trustno1",
        "1q2w3e4r",
        "1qaz2wsx",
        "qazwsx123",
        "zaq12wsx",
        "asdf1234",
        "passw0rd",
        "p@ssw0rd",
        "admin123",
        "root1234",
        "user1234",
        "test1234",
        "guest123",
        "login123",
        "starwars1",
        "whatever1",
        "freedom1",
        "charlie1",
        "aa123456",
        "a1234567",
        "abcd1234",
        "1234qwer",
        "q1w2e3r4",
        "147258369",
        "987654321",
        "11111111",
    }
)


def validate_password_strength(password: str) -> None:
    """Enforce the registration password policy. Raises PasswordTooWeak."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise PasswordTooWeak(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if not (any(c.isalpha() for c in password) and any(c.isdigit() for c in password)):
        raise PasswordTooWeak("Password must contain a mix of letters and numbers.")
    if password.lower() in COMMON_PASSWORDS:
        raise PasswordTooWeak("This password is too common. Please choose a stronger one.")
