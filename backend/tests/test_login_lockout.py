"""Login lockout: unit tests with fake ports + API tests through /api/auth/login.

The API tests exercise the real Redis tracker (conftest clears
login_lockout:* keys before each test); the unit tests pin the use-case
logic with an in-memory tracker.
"""

import pytest

from app.core.config import settings
from app.domains.auth.application.use_cases import LoginUser
from app.domains.auth.domain import AccountTemporarilyLocked, InvalidCredentials, User
from tests.helpers import PASSWORD, login, register

pytestmark = pytest.mark.asyncio


class FakeUsers:
    def __init__(self, user: User | None) -> None:
        self._user = user
        self.get_by_email_calls = 0

    async def get_by_email(self, email: str) -> User | None:
        self.get_by_email_calls += 1
        return self._user


class FakeRefreshTokens:
    async def add(self, token) -> None:
        pass


class FakeHasher:
    def hash(self, password: str) -> str:
        return f"h:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"h:{password}"


class FakeTokens:
    def create_access_token(self, user_id: str) -> str:
        return f"access:{user_id}"

    def new_opaque_token(self) -> tuple[str, str]:
        return ("raw", "h:raw")


class FakeTracker:
    """Keyed like the real tracker. `locked_for` forces every key locked."""

    def __init__(self, *, locked_for: int = 0) -> None:
        self.locked_for = locked_for
        self.fails: dict[str, int] = {}
        self.locks: set[str] = set()
        self.cleared: set[str] = set()

    async def lockout_remaining(self, key: str) -> int:
        return self.locked_for or (600 if key in self.locks else 0)

    async def record_failure(self, key: str) -> int:
        self.fails[key] = self.fails.get(key, 0) + 1
        return self.fails[key]

    async def lock(self, key: str) -> None:
        self.locks.add(key)
        self.fails.pop(key, None)

    async def clear(self, key: str) -> None:
        self.cleared.add(key)
        self.fails.pop(key, None)
        self.locks.discard(key)


EMAIL = "user@example.com"


def client_key(ip: str | None = None, email: str = EMAIL) -> str:
    return f"{email}|{ip or 'unknown'}"


class FakeAudit:
    def __init__(self) -> None:
        self.events = []

    async def record(self, event) -> None:
        self.events.append(event)


def make_login(
    user: User | None,
    tracker: FakeTracker,
    audit: FakeAudit | None = None,
    *,
    account_max: int = 0,
):
    users = FakeUsers(user)
    use_case = LoginUser(
        users,
        FakeRefreshTokens(),
        FakeHasher(),
        FakeTokens(),
        30,
        tracker,
        audit or FakeAudit(),
        max_failed_attempts=5,
        account_max_failed_attempts=account_max,
    )
    return use_case, users


def make_user(email: str = "user@example.com") -> User:
    return User(email=email, password_hash=f"h:{PASSWORD}", first_name="Test")


async def test_locked_key_raises_before_any_lookup():
    tracker = FakeTracker(locked_for=600)
    use_case, users = make_login(make_user(), tracker)
    with pytest.raises(AccountTemporarilyLocked) as exc_info:
        await use_case.execute("user@example.com", PASSWORD)
    assert exc_info.value.retry_after == 600
    # No DB or argon2 work happened — locked accounts stay timing-uniform.
    assert users.get_by_email_calls == 0


async def test_threshold_failure_locks():
    tracker = FakeTracker()
    tracker.fails[client_key()] = 4  # four earlier misses within the window
    use_case, _ = make_login(make_user(), tracker)
    with pytest.raises(InvalidCredentials):
        await use_case.execute("user@example.com", "wrong-password1")
    assert tracker.locks == {client_key()}


async def test_success_clears_counter():
    tracker = FakeTracker()
    use_case, _ = make_login(make_user(), tracker)
    await use_case.execute("user@example.com", PASSWORD)
    assert tracker.cleared == {client_key(), EMAIL}


async def test_attacker_ip_lockout_does_not_lock_out_the_owner():
    """The lockout-DoS regression: five wrong guesses from one IP lock that
    IP only — the owner, on another IP, still signs in."""
    tracker = FakeTracker()
    use_case, _ = make_login(make_user(), tracker, account_max=50)
    for _ in range(5):
        with pytest.raises(InvalidCredentials):
            await use_case.execute(EMAIL, "wrong-password1", ip="203.0.113.9")
    with pytest.raises(AccountTemporarilyLocked):
        await use_case.execute(EMAIL, PASSWORD, ip="203.0.113.9")
    user, _, _ = await use_case.execute(EMAIL, PASSWORD, ip="198.51.100.7")
    assert user.email == EMAIL


async def test_distributed_guessing_hits_the_account_wide_cap():
    """Rotating IPs dodges the per-client lock but not the per-email one."""
    tracker = FakeTracker()
    audit = FakeAudit()
    use_case, _ = make_login(make_user(), tracker, audit, account_max=8)
    for i in range(8):
        with pytest.raises(InvalidCredentials):
            await use_case.execute(EMAIL, "wrong-password1", ip=f"203.0.113.{i}")
    assert EMAIL in tracker.locks
    with pytest.raises(AccountTemporarilyLocked):
        await use_case.execute(EMAIL, PASSWORD, ip="198.51.100.7")
    lockouts = [e for e in audit.events if e.action == "auth.lockout_triggered"]
    assert [e.meta["scope"] for e in lockouts] == ["account"]


async def test_account_wide_cap_disabled_with_zero():
    tracker = FakeTracker()
    use_case, _ = make_login(make_user(), tracker, account_max=0)
    for i in range(30):
        with pytest.raises(InvalidCredentials):
            await use_case.execute(EMAIL, "wrong-password1", ip=f"203.0.113.{i}")
    assert not tracker.locks


async def test_password_reset_lifts_the_lock():
    from app.domains.auth.application.use_cases import ResetPassword

    user = make_user()
    tracker = FakeTracker()
    tracker.locks |= {EMAIL, client_key("198.51.100.7")}

    class Users:
        async def get(self, user_id):
            return user

    class RefreshTokens:
        async def revoke_all_for_user(self, user_id) -> None:
            pass

    class Tokens(FakeTokens):
        def hash_token(self, value: str) -> str:
            return f"fingerprint-of-{value}"

        def decode_action_token(self, token, purpose):
            return {"sub": str(user.id), "pwd": self.hash_token(user.password_hash)[:16]}

    class Mailer:
        async def send_password_changed(self, user) -> None:
            pass

    await ResetPassword(
        Users(), RefreshTokens(), FakeHasher(), Tokens(), FakeAudit(), Mailer(), tracker
    ).execute(
        token="t",
        password="New_password2",
        password_confirmation="New_password2",
        ip="198.51.100.7",
    )
    assert not tracker.locks


async def test_unknown_email_counts_like_wrong_password():
    tracker = FakeTracker()
    use_case, _ = make_login(None, tracker)
    with pytest.raises(InvalidCredentials):
        await use_case.execute("ghost@example.com", PASSWORD)
    assert tracker.fails == {client_key(email="ghost@example.com"): 1, "ghost@example.com": 1}
    assert not tracker.locks


async def test_lockout_key_normalizes_email():
    class KeyCapturingTracker(FakeTracker):
        def __init__(self) -> None:
            super().__init__(locked_for=60)
            self.seen_keys = []

        async def lockout_remaining(self, key: str) -> int:
            self.seen_keys.append(key)
            return self.locked_for

    capturing = KeyCapturingTracker()
    use_case, _ = make_login(make_user(), capturing)
    with pytest.raises(AccountTemporarilyLocked):
        await use_case.execute("  User@Example.COM ", PASSWORD, ip="1.2.3.4")
    assert capturing.seen_keys == ["user@example.com|1.2.3.4", "user@example.com"]


# ── API (real Redis tracker) ─────────────────────────────────────────


async def test_lockout_after_max_failures_even_with_correct_password(client):
    await register(client, "locked@example.com")
    for _ in range(settings.login_lockout_max_attempts):
        res = await login(client, "locked@example.com", "wrong-password1")
        assert res.status_code == 401, res.text
        assert res.json()["code"] == "ERR_AUTH_001"
    # The right password no longer helps — the lock, not the check, answers.
    res = await login(client, "locked@example.com")
    assert res.status_code == 429, res.text
    assert res.json()["code"] == "ERR_AUTH_006"
    assert int(res.headers["Retry-After"]) > 0


async def test_unregistered_email_locks_identically(client):
    """Enumeration check: an email with no account behaves exactly like a
    real one — same 401s, then the same 429."""
    for _ in range(settings.login_lockout_max_attempts):
        res = await login(client, "nobody@example.com", "wrong-password1")
        assert res.status_code == 401, res.text
    res = await login(client, "nobody@example.com", "wrong-password1")
    assert res.status_code == 429, res.text
    assert res.json()["code"] == "ERR_AUTH_006"


async def test_success_resets_failure_count(client):
    await register(client, "resets@example.com")
    for _ in range(settings.login_lockout_max_attempts - 1):
        res = await login(client, "resets@example.com", "wrong-password1")
        assert res.status_code == 401
    res = await login(client, "resets@example.com")
    assert res.status_code == 200, res.text
    # Counter is back at zero: another single failure doesn't lock.
    res = await login(client, "resets@example.com", "wrong-password1")
    assert res.status_code == 401, res.text
    res = await login(client, "resets@example.com")
    assert res.status_code == 200, res.text
