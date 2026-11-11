"""Per-checkout secrets for the local dev stack.

The template is public, so any value committed to it (the placeholder
SECRET_KEY, a seed password) is known to everyone — and the dev API port is
published on the LAN for device testing. Local stacks therefore never run on
committed values: the first process that needs a secret generates a random
one and stores it under ``backend/.dev-secrets/`` (gitignored and
dockerignored). backend, worker, and beat mount the same directory, so they
agree on the value and it survives restarts.

Never used in production — config.py refuses to boot there without a real
SECRET_KEY, and seed_dev.py refuses to run off a local stack.
"""

import logging
import os
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

# backend/.dev-secrets (this file is backend/app/core/dev_secrets.py).
DEV_SECRETS_DIR = Path(__file__).resolve().parents[2] / ".dev-secrets"


def _read(path: Path) -> str:
    # The creating process may still be between O_EXCL-create and write.
    for _ in range(20):
        value = path.read_text().strip()
        if value:
            return value
        time.sleep(0.05)
    return ""


def load_or_create(name: str, factory: Callable[[], str]) -> str:
    """Return the stored secret `name`, generating it on first use.

    Creation is exclusive (O_EXCL), so concurrently starting processes all
    end up with the one value that won the race. If the directory is not
    writable the secret is random per process: still unguessable, but not
    shared — tokens signed by one process won't verify in another."""
    path = DEV_SECRETS_DIR / name
    try:
        if path.exists() and (value := _read(path)):
            return value
        DEV_SECRETS_DIR.mkdir(mode=0o700, exist_ok=True)
        value = factory()
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return _read(path) or value
        with os.fdopen(fd, "w") as fh:
            fh.write(value + "\n")
        return value
    except OSError:
        logger.warning(
            "dev secret %r: %s is not writable — using a per-process random value",
            name,
            DEV_SECRETS_DIR,
            exc_info=True,
        )
        return factory()
