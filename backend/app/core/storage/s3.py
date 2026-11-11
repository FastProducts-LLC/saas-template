"""S3-compatible object storage with an injected synchronous SDK client."""

import asyncio
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from botocore.exceptions import BotoCoreError, ClientError

from app.core.storage.base import (
    ObjectInfo,
    PresignedUpload,
    StorageError,
    StorageObjectNotFound,
)
from app.core.storage.keys import validate_key


class S3FileStorage:
    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket

    async def _call(self, operation, *, missing_is_not_found: bool = False):
        try:
            return await asyncio.to_thread(operation)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if missing_is_not_found and (code in {"NoSuchKey", "404"} or status == 404):
                raise StorageObjectNotFound("Storage object not found") from exc
            raise StorageError("S3 storage operation failed") from exc
        except BotoCoreError as exc:
            raise StorageError("S3 storage operation failed") from exc

    async def put(self, key: str, data: bytes, *, content_type: str) -> None:
        validate_key(key)
        await self._call(
            lambda: self.client.put_object(
                Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
            )
        )

    async def get(self, key: str) -> bytes:
        validate_key(key)

        def read():
            body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"]
            try:
                return body.read()
            finally:
                body.close()

        return await self._call(read, missing_is_not_found=True)

    async def stat(self, key: str) -> ObjectInfo | None:
        validate_key(key)
        try:
            response = await self._call(
                lambda: self.client.head_object(Bucket=self.bucket, Key=key),
                missing_is_not_found=True,
            )
        except StorageObjectNotFound:
            return None
        return ObjectInfo(key, response["ContentLength"], response.get("ContentType"))

    async def delete(self, key: str) -> None:
        validate_key(key)
        await self._call(lambda: self.client.delete_object(Bucket=self.bucket, Key=key))

    async def presigned_get(self, key: str, *, ttl: timedelta, filename: str | None = None) -> str:
        validate_key(key)
        params = {"Bucket": self.bucket, "Key": key}
        if filename is not None:
            # RFC 5987 encoding avoids header injection and supports Unicode names.
            params["ResponseContentDisposition"] = (
                f"attachment; filename*=UTF-8''{quote(filename, safe='')}"
            )
        return await self._call(
            lambda: self.client.generate_presigned_url(
                "get_object", Params=params, ExpiresIn=int(ttl.total_seconds())
            )
        )

    async def presigned_put(
        self, key: str, *, content_type: str, max_bytes: int, ttl: timedelta
    ) -> PresignedUpload:
        """Sign a PUT; the caller must enforce max_bytes at confirm time via stat.

        S3 presigned PUT URLs cannot cap the uploaded body size.
        """
        validate_key(key)
        url = await self._call(
            lambda: self.client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=int(ttl.total_seconds()),
            )
        )
        return PresignedUpload(
            url=url,
            method="PUT",
            headers={"Content-Type": content_type},
            expires_at=datetime.now(UTC) + ttl,
        )
