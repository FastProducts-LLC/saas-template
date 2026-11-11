"""Shared test fixtures.

Tests run inside Docker against an isolated `app_test` database created on the
same Postgres server the dev stack uses:

    docker compose exec backend pytest

The app's per-request `get_db` is overridden to hit the test database; tables
are created from the ORM metadata (not migrations — alembic owns those) and
emptied between tests. The rate limiter is disabled so tests can hit auth
endpoints freely.
"""

import asyncio
import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.ratelimit import limiter
from app.domains.audit.infrastructure.recorder import AutonomousAuditRecorder
from app.domains.audit.interface.deps import get_audit_recorder
from app.domains.auth.infrastructure.session_revoker import AutonomousSessionRevoker
from app.domains.auth.interface.deps import get_session_revoker
from app.main import app

# Override when concurrent pytest runs would clobber each other's rows:
#   docker compose exec -e TEST_DB_NAME=app_test_b backend pytest
TEST_DB_NAME = os.environ.get("TEST_DB_NAME", "app_test")


def _test_db_url() -> str:
    base, _, _ = settings.database_url.rpartition("/")
    return f"{base}/{TEST_DB_NAME}"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    # CREATE DATABASE cannot run inside a transaction — use autocommit.
    admin = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_NAME}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    await admin.dispose()

    engine = create_async_engine(_test_db_url())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _wire_app(test_engine):
    """Point the app at the test database and disable rate limiting."""
    limiter.enabled = False
    test_sessionmaker = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _get_db():
        # Mirrors app.core.database.get_db: one transaction per request.
        async with test_sessionmaker() as session:
            async with session.begin():
                yield session

    app.dependency_overrides[get_db] = _get_db
    # The audit recorder opens its own sessions (autonomous transactions) —
    # bind it to the test DB or its FK targets wouldn't exist there.
    app.dependency_overrides[get_audit_recorder] = lambda: AutonomousAuditRecorder(
        test_sessionmaker
    )
    # Same for refresh-token reuse detection (revokes in its own transaction).
    app.dependency_overrides[get_session_revoker] = lambda: AutonomousSessionRevoker(
        test_sessionmaker
    )
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(test_engine):
    """Start each test from an empty database (reverse FK order).

    Cleanup is intentionally before the test, not after it. ASGI middleware and
    yield-dependency finalizers can finish on the next event-loop turn after
    the response is observed by the test client; deleting rows immediately
    after a test can race those finalizers and produce false StaleDataError /
    FK failures inside otherwise completed requests.
    """
    await asyncio.sleep(0)
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield


@pytest_asyncio.fixture(autouse=True)
async def _clear_lockout_keys():
    """Failed-login tests share emails across runs; leftover lockout counters
    in real Redis would start 429-ing them within the 15-minute window."""
    try:
        from app.core.error_handling import _redis_client

        redis = _redis_client()
        keys = [key async for key in redis.scan_iter(match="login_lockout:*")]
        if keys:
            await redis.delete(*keys)
    except Exception:
        pass  # no Redis (unit-only run) — the tracker falls back to in-memory
    yield


@pytest_asyncio.fixture
async def db(test_engine):
    """Direct database access for assertions on persisted state."""
    test_sessionmaker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with test_sessionmaker() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    # raise_app_exceptions=False: behave like a real HTTP client — unhandled
    # server errors come back as the rendered 500 response, not a re-raise.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
