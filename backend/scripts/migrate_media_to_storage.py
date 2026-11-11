"""Copy existing generation assets into configured storage, preserving their keys.

Run from any directory: python backend/scripts/migrate_media_to_storage.py --dry-run
Rows and local source files are never modified. Re-runs skip equal-sized objects.
"""

import argparse
import asyncio
import sys
from pathlib import Path


async def migrate(*, dry_run: bool) -> int:
    from app.core.config import settings

    if settings.storage_provider == "local":
        print("Nothing to migrate: set STORAGE_PROVIDER=s3 first.", file=sys.stderr)
        return 2

    from sqlalchemy import select

    from app.core.database import SessionLocal, engine
    from app.core.storage import LocalFileStorage, get_file_storage
    from app.core.storage.base import StorageObjectNotFound
    from app.domains.generations.infrastructure.orm import generations_table

    source = LocalFileStorage(Path(settings.media_dir))
    destination = get_file_storage()
    copied = skipped = missing = failed = would_copy = 0
    try:
        async with SessionLocal() as session:
            rows = await session.stream(
                select(
                    generations_table.c.id,
                    generations_table.c.file_path,
                    generations_table.c.mime_type,
                ).where(generations_table.c.file_path.is_not(None))
            )
            async for row in rows:
                try:
                    info = await source.stat(row.file_path)
                    if info is None:
                        missing += 1
                        continue
                    existing = await destination.stat(row.file_path)
                    if existing is not None and existing.size_bytes == info.size_bytes:
                        skipped += 1
                        continue
                    if dry_run:
                        would_copy += 1
                        print(f"Would copy generation {row.id}")
                        continue
                    data = await source.get(row.file_path)
                    await destination.put(
                        row.file_path,
                        data,
                        content_type=row.mime_type
                        or info.content_type
                        or "application/octet-stream",
                    )
                    copied += 1
                except StorageObjectNotFound:
                    missing += 1
                except Exception:
                    # SDK exception messages can contain credentials or signed URLs.
                    failed += 1
                    print(f"Copy failed for generation {row.id}", file=sys.stderr)
    finally:
        await engine.dispose()
    print(
        f"copied={copied} / skipped={skipped} / missing={missing} / "
        f"failed={failed} / would_copy={would_copy}"
    )
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Report copies without writing objects"
    )
    args = parser.parse_args()
    # Match the other standalone backend scripts without requiring package installation.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    return asyncio.run(migrate(dry_run=args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
