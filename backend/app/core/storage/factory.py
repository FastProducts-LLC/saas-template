"""Process-wide storage provider selection; the S3 SDK is built lazily."""

from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.core.storage.base import FileStorage
from app.core.storage.local import LocalFileStorage


def build_s3_client():
    import boto3
    from botocore.config import Config

    options = {
        "region_name": settings.s3_region,
        "aws_access_key_id": settings.s3_access_key_id,
        "aws_secret_access_key": settings.s3_secret_access_key,
        "config": Config(
            signature_version="s3v4",
            connect_timeout=5,
            read_timeout=30,
            retries={"mode": "standard", "total_max_attempts": 3},
        ),
    }
    if settings.s3_endpoint_url:
        options["endpoint_url"] = settings.s3_endpoint_url
    return boto3.client("s3", **options)


@lru_cache(maxsize=1)
def get_file_storage() -> FileStorage:
    if settings.storage_provider == "local":
        return LocalFileStorage(Path(settings.media_dir))
    if settings.storage_provider == "s3":
        from app.core.storage.s3 import S3FileStorage

        return S3FileStorage(build_s3_client(), settings.s3_bucket)
    raise ValueError("Unsupported storage provider")


def reset_file_storage_cache() -> None:
    get_file_storage.cache_clear()
