"""Transport-neutral generation download result."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MediaDownload:
    mime_type: str
    data: bytes


@dataclass(frozen=True)
class MediaFileUrl:
    url: str | None
    expires_in: int | None
