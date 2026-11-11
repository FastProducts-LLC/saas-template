"""S3 configuration is mandatory in every environment when selected."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

S3_SETTINGS = {
    "s3_bucket": "test-bucket",
    "s3_region": "test-region",
    "s3_access_key_id": "test-access-key",
    "s3_secret_access_key": "test-secret-key",
}


def _settings(**overrides):
    base = {
        "environment": "development",
        "secret_key": "s" * 48,
        "frontend_url": "https://app.example.com",
        "cors_origins": ["https://app.example.com"],
        "email_provider": "smtp",
        "stripe_secret_key": "",
        "storage_provider": "local",
        "s3_endpoint_url": "",
        **dict.fromkeys(S3_SETTINGS, ""),
    }
    return Settings(_env_file=None, **{**base, **overrides})


@pytest.mark.parametrize("environment", ["development", "production"])
@pytest.mark.parametrize("missing", S3_SETTINGS)
@pytest.mark.parametrize("empty", ["", "   "])
def test_s3_provider_requires_bucket_and_credentials(environment, missing, empty):
    with pytest.raises(ValidationError, match=missing.upper()):
        _settings(
            environment=environment,
            storage_provider="s3",
            **{**S3_SETTINGS, missing: empty},
        )


@pytest.mark.parametrize("environment", ["development", "production"])
def test_local_provider_needs_no_s3_settings(environment):
    settings = _settings(environment=environment)
    assert settings.storage_provider == "local"
    for field in S3_SETTINGS:
        assert getattr(settings, field) == ""


@pytest.mark.parametrize("environment", ["development", "production"])
@pytest.mark.parametrize("endpoint", ["", "https://nyc3.digitaloceanspaces.com"])
def test_s3_endpoint_is_optional(environment, endpoint):
    settings = _settings(
        environment=environment,
        storage_provider="s3",
        s3_endpoint_url=endpoint,
        **S3_SETTINGS,
    )
    assert settings.s3_endpoint_url == endpoint
