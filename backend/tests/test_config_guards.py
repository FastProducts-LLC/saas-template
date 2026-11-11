"""Settings guards: a placeholder SECRET_KEY must never sign tokens for a
deployment that is reachable beyond a developer machine — even when
ENVIRONMENT was left at its "development" default."""

import pytest
from pydantic import ValidationError

from app.core import dev_secrets
from app.core.config import _INSECURE_SECRET_KEYS, Settings, _is_local_url

PLACEHOLDER = "change-me-in-production"
STRONG = "s" * 48


def _settings(**overrides) -> Settings:
    base = {
        "environment": "development",
        "secret_key": PLACEHOLDER,
        "frontend_url": "http://localhost:21427",
        "cors_origins": ["http://localhost:21427"],
        "stripe_secret_key": "",
    }
    return Settings(_env_file=None, **{**base, **overrides})


@pytest.fixture(autouse=True)
def _isolated_dev_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(dev_secrets, "DEV_SECRETS_DIR", tmp_path / ".dev-secrets")


@pytest.mark.parametrize("placeholder", sorted(_INSECURE_SECRET_KEYS))
def test_placeholder_secret_never_signs_on_localhost(placeholder):
    """The placeholder is public (the template is), and the dev API port is
    LAN-reachable — a local stack swaps in a random per-checkout key."""
    key = _settings(secret_key=placeholder).secret_key
    assert key not in _INSECURE_SECRET_KEYS and len(key) >= 64
    # Stable: backend, worker, and beat (and every restart) agree on it.
    assert _settings(secret_key=placeholder).secret_key == key
    assert (dev_secrets.DEV_SECRETS_DIR / "secret_key").stat().st_mode & 0o077 == 0


def test_dev_secret_falls_back_to_random_when_dir_unwritable(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setattr(dev_secrets, "DEV_SECRETS_DIR", blocker / "nope")
    key = _settings().secret_key
    assert key not in _INSECURE_SECRET_KEYS and len(key) >= 64


def test_explicit_dev_secret_is_left_alone():
    assert _settings(secret_key=STRONG).secret_key == STRONG
    assert not dev_secrets.DEV_SECRETS_DIR.exists()


@pytest.mark.parametrize("environment", ["development", "production"])
def test_placeholder_previous_key_is_rejected_everywhere(environment):
    with pytest.raises(ValidationError, match="SECRET_KEY_PREVIOUS"):
        _settings(environment=environment, secret_key=STRONG, secret_key_previous=PLACEHOLDER)


@pytest.mark.parametrize(
    "url",
    [
        "http://192.168.1.20:21427",
        "http://127.0.0.1:21427",
        "http://myapp.test",
        "http://frontend:5173",
    ],
)
def test_placeholder_secret_is_fine_on_private_hosts(url):
    assert _settings(frontend_url=url, cors_origins=[url])


@pytest.mark.parametrize(
    "overrides",
    [
        {"frontend_url": "https://app.acme.com"},
        {"cors_origins": ["http://localhost:21427", "https://app.acme.com"]},
        {"stripe_secret_key": "sk_live_abc"},
        {"stripe_secret_key": "rk_live_abc"},
        {"secret_key": "change-me-generate-a-long-random-string", "frontend_url": "https://x.io"},
        {"secret_key": "", "frontend_url": "https://x.io"},
    ],
)
def test_placeholder_secret_refuses_to_boot_on_a_real_deployment(overrides):
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _settings(**overrides)


def test_real_secret_boots_in_development_with_public_url():
    assert _settings(secret_key=STRONG, frontend_url="https://staging.acme.com")


def test_production_guard_still_rejects_placeholder():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _settings(
            environment="production",
            frontend_url="https://app.acme.com",
            cors_origins=["https://app.acme.com"],
        )


def test_is_local_url():
    assert _is_local_url("http://localhost:3000")
    assert _is_local_url("http://[::1]:3000")
    assert _is_local_url("http://10.0.2.2:21428")
    assert not _is_local_url("https://example.com")
    assert not _is_local_url("http://8.8.8.8")
