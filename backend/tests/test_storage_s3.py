"""S3 contract tests using a real SDK client without network requests."""

import io
from datetime import timedelta
from urllib.parse import parse_qs, unquote, urlsplit

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import EndpointConnectionError
from botocore.response import StreamingBody
from botocore.stub import Stubber

from app.core.storage.base import StorageError, StorageObjectNotFound
from app.core.storage.s3 import S3FileStorage

BUCKET = "test-bucket"
KEY = "org/test/generations/result.png"
TTL = timedelta(seconds=123)


@pytest.fixture
def s3():
    client = boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        endpoint_url="https://objects.example.test",
        config=Config(signature_version="s3v4"),
    )
    with Stubber(client) as stubber:
        yield S3FileStorage(client, BUCKET), stubber
        stubber.assert_no_pending_responses()
    client.close()


async def test_put_sends_bucket_key_content_type(s3):
    storage, stubber = s3
    stubber.add_response(
        "put_object",
        {},
        {
            "Bucket": BUCKET,
            "Key": KEY,
            "Body": b"data",
            "ContentType": "image/png",
        },
    )
    await storage.put(KEY, b"data", content_type="image/png")


async def test_get_missing_maps_to_not_found(s3):
    storage, stubber = s3
    stubber.add_client_error(
        "get_object",
        service_error_code="NoSuchKey",
        http_status_code=404,
        expected_params={"Bucket": BUCKET, "Key": KEY},
    )
    with pytest.raises(StorageObjectNotFound):
        await storage.get(KEY)


async def test_stat_missing_returns_none(s3):
    storage, stubber = s3
    stubber.add_client_error(
        "head_object",
        service_error_code="404",
        http_status_code=404,
        expected_params={"Bucket": BUCKET, "Key": KEY},
    )
    assert await storage.stat(KEY) is None


async def test_delete_missing_is_not_an_error(s3):
    storage, stubber = s3
    for _ in range(2):
        stubber.add_response("delete_object", {}, {"Bucket": BUCKET, "Key": KEY})
        await storage.delete(KEY)


async def test_presigned_get_contains_key_and_expiry(s3):
    storage, _ = s3
    filename = 'a "quoted" image\r\n.png'
    url = await storage.presigned_get(KEY, ttl=TTL, filename=filename)
    parsed = urlsplit(url)
    assert unquote(parsed.path).endswith("/" + KEY)
    query = parse_qs(parsed.query)
    assert query["X-Amz-Expires"] == ["123"]
    disposition = query["response-content-disposition"][0]
    assert disposition.startswith("attachment; filename*=UTF-8''")
    assert unquote(disposition.split("''", 1)[1]) == filename
    assert "\r" not in disposition and "\n" not in disposition


async def test_presigned_put_requires_content_type_header(s3):
    storage, _ = s3
    upload = await storage.presigned_put(KEY, content_type="image/png", max_bytes=123, ttl=TTL)
    assert upload.headers == {"Content-Type": "image/png"}
    assert upload.method == "PUT"
    assert upload.expires_at.tzinfo is not None
    query = parse_qs(urlsplit(upload.url).query)
    assert "content-type" in query["X-Amz-SignedHeaders"][0].split(";")
    assert query["X-Amz-Expires"] == ["123"]


@pytest.mark.parametrize("operation", ["put", "get", "stat", "delete"])
async def test_client_error_maps_to_storage_error(s3, operation):
    storage, stubber = s3
    sdk_operation = {
        "put": "put_object",
        "get": "get_object",
        "stat": "head_object",
        "delete": "delete_object",
    }[operation]
    stubber.add_client_error(sdk_operation, service_error_code="AccessDenied", http_status_code=403)
    with pytest.raises(StorageError, match="S3 storage operation failed") as error:
        if operation == "put":
            await storage.put(KEY, b"data", content_type="image/png")
        else:
            await getattr(storage, operation)(KEY)
    assert error.value.__cause__ is not None
    assert not isinstance(error.value, StorageObjectNotFound)


async def test_get_reads_and_closes_body(s3):
    storage, stubber = s3
    raw = io.BytesIO(b"data")
    stubber.add_response(
        "get_object",
        {"Body": StreamingBody(raw, 4)},
        {
            "Bucket": BUCKET,
            "Key": KEY,
        },
    )
    assert await storage.get(KEY) == b"data"
    assert raw.closed


async def test_stat_reports_metadata(s3):
    storage, stubber = s3
    stubber.add_response(
        "head_object",
        {"ContentLength": 4, "ContentType": "image/png"},
        {
            "Bucket": BUCKET,
            "Key": KEY,
        },
    )
    info = await storage.stat(KEY)
    assert (info.key, info.size_bytes, info.content_type) == (KEY, 4, "image/png")


async def test_sdk_error_during_presigning_is_wrapped(s3, monkeypatch):
    storage, _ = s3

    def fail(*args, **kwargs):
        raise EndpointConnectionError(endpoint_url="https://objects.example.test")

    monkeypatch.setattr(storage.client, "generate_presigned_url", fail)
    with pytest.raises(StorageError, match="S3 storage operation failed"):
        await storage.presigned_get(KEY, ttl=TTL)
