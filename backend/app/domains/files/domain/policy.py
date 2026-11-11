"""Purpose-specific upload rules, independent of HTTP and persistence."""

from dataclasses import dataclass
from typing import Literal

from app.core.policy import UPLOAD_AVATAR_MAX_BYTES, UPLOAD_AVATAR_MAX_FILES
from app.domains.files.domain.entities import FilePurpose


@dataclass(frozen=True)
class FileRules:
    content_types: frozenset[str]
    max_bytes: int
    max_files_per_owner: int
    owner: Literal["user", "organization"]
    public: bool
    area: str


FILE_RULES = {
    FilePurpose.AVATAR: FileRules(
        content_types=frozenset({"image/png", "image/jpeg", "image/webp"}),
        max_bytes=UPLOAD_AVATAR_MAX_BYTES,
        max_files_per_owner=UPLOAD_AVATAR_MAX_FILES,
        owner="user",
        public=True,
        area="avatars",
    ),
}

CONTENT_TYPE_EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def sniff_image_type(head: bytes) -> str | None:
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None
