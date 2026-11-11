"""Audit composition root.

`get_audit_recorder` is a FastAPI dependency so tests can override it to bind
the recorder to the test database; other slices receive it structurally
through their own AuditRecorder ports.
"""

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.database import SessionLocal
from app.domains.audit.infrastructure.recorder import AutonomousAuditRecorder


def build_audit_recorder(session_factory: async_sessionmaker) -> AutonomousAuditRecorder:
    """For background-job composition roots (workers) and tests."""
    return AutonomousAuditRecorder(session_factory)


def get_audit_recorder() -> AutonomousAuditRecorder:
    return build_audit_recorder(SessionLocal)
