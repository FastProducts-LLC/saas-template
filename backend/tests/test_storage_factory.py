"""Storage provider selection and lazy SDK construction."""

from unittest.mock import Mock

import pytest

from app.core.config import settings
from app.core.storage import LocalFileStorage, S3FileStorage, factory


@pytest.fixture(autouse=True)
def reset_cache():
    factory.reset_file_storage_cache()
    yield
    factory.reset_file_storage_cache()


def test_factory_returns_local_by_default(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "storage_provider", "local")
    monkeypatch.setattr(settings, "media_dir", str(tmp_path))
    storage = factory.get_file_storage()
    assert isinstance(storage, LocalFileStorage)
    assert storage.root == tmp_path
    assert factory.get_file_storage() is storage


def test_factory_returns_s3_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "storage_provider", "s3")
    monkeypatch.setattr(settings, "s3_bucket", "test-bucket")
    client = object()
    build = Mock(return_value=client)
    monkeypatch.setattr(factory, "build_s3_client", build)
    storage = factory.get_file_storage()
    assert isinstance(storage, S3FileStorage)
    assert storage.client is client
    assert storage.bucket == "test-bucket"
    assert factory.get_file_storage() is storage
    build.assert_called_once_with()


@pytest.mark.parametrize("endpoint", ["", "https://objects.example.test"])
def test_build_s3_client_uses_settings(monkeypatch, endpoint):
    import boto3

    fields = {
        "s3_region": "us-east-1",
        "s3_access_key_id": "testing",
        "s3_secret_access_key": "testing",
        "s3_endpoint_url": endpoint,
    }
    for field, value in fields.items():
        monkeypatch.setattr(settings, field, value)
    build = Mock()
    monkeypatch.setattr(boto3, "client", build)
    assert factory.build_s3_client() is build.return_value
    args, kwargs = build.call_args
    assert args == ("s3",)
    assert kwargs["region_name"] == "us-east-1"
    assert kwargs["aws_access_key_id"] == "testing"
    assert kwargs["aws_secret_access_key"] == "testing"
    assert kwargs["config"].signature_version == "s3v4"
    assert kwargs["config"].connect_timeout == 5
    assert kwargs["config"].read_timeout == 30
    assert kwargs["config"].retries["total_max_attempts"] == 3
    if endpoint:
        assert kwargs["endpoint_url"] == endpoint
    else:
        assert "endpoint_url" not in kwargs
