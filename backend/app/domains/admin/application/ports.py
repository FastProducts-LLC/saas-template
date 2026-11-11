"""Admin application ports — cross-tenant read queries + moderation.

Unlike every other repository port in the codebase, these queries are
deliberately NOT scoped by organization_id — they power the superuser-only
admin views. Do not import this from tenant-facing slices.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domains.admin.domain import AdminAuditEntry
from app.domains.auth.domain import User
from app.domains.credits.domain import CreditAction, CreditWallet
from app.domains.generations.domain import Generation, GenerationStatus
from app.domains.organizations.domain import Invitation, Organization

# ── Analytics data shapes (for the overview dashboard charts) ─────────────────


@dataclass(frozen=True)
class TimeseriesPoint:
    """One day-bucketed count for a line/spark chart."""

    date: str  # ISO date YYYY-MM-DD
    count: int


@dataclass(frozen=True)
class CategoryCount:
    """One label-count pair for a breakdown (donut / stacked bar)."""

    label: str
    count: int


@dataclass(frozen=True)
class TopCustomer:
    """One org + a metric value for a top-N bar chart."""

    name: str
    value: int


@dataclass(frozen=True)
class CreditSummary:
    """Platform-wide credit totals for the overview counters."""

    total_balance: int
    total_pending_holds: int
    total_credits_captured: int


@dataclass(frozen=True)
class CommercialSummary:
    """Commercial and credit-risk counters for platform operations."""

    organizations_with_billing_account: int
    organizations_with_wallet: int
    negative_wallets: int
    zero_balance_wallets: int
    low_balance_wallets: int
    low_balance_threshold: int


@dataclass(frozen=True)
class OperationsSummary:
    """Backlog and stuck-work counters admins need to clear."""

    pending_invitations: int
    expired_invitations: int
    open_privacy_requests: int
    overdue_privacy_requests: int
    privacy_requests_due_soon: int
    stale_pending_generations: int
    expired_credit_holds: int


@dataclass(frozen=True)
class SecuritySummary:
    """Account and credential posture for the platform admin overview."""

    superusers: int
    email_verified_users: int
    unverified_users: int
    email_suppressed_users: int
    active_api_keys: int
    api_keys_used_30d: int
    stale_api_keys: int
    unused_api_keys: int


@dataclass(frozen=True)
class Analytics:
    """Aggregated platform analytics for the admin overview dashboard."""

    user_signups: list[TimeseriesPoint]
    org_signups: list[TimeseriesPoint]
    credits_spent_daily: list[TimeseriesPoint]
    generations_by_status: list[CategoryCount]
    generations_by_kind: list[CategoryCount]
    top_customers_by_credits: list[TopCustomer]
    credit_summary: CreditSummary
    commercial_summary: CommercialSummary
    operations_summary: OperationsSummary
    security_summary: SecuritySummary
    recent_admin_actions: list[CategoryCount]


@dataclass(frozen=True)
class CustomerUsageRow:
    """One org on the founder customers view — accounts and credit spend."""

    organization_id: uuid.UUID
    organization_name: str
    organization_slug: str
    created_at: datetime
    suspended_at: datetime | None
    member_count: int
    owner_email: str | None
    owner_name: str | None
    credits_spent: int  # sum of captured holds
    credit_balance: int | None  # None when the org has never touched credits


# ── Minimal views of other slices' behavior (satisfied structurally by
# auth's refresh-token repository and the credit engine — same pattern as
# generations' CreditService port) ─────────────────────────────────────────────


class SessionRevoker(Protocol):
    """Kill every session for a user (moderation: deactivate / sign out)."""

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None: ...


class CreditAdjuster(Protocol):
    """Manual wallet correction by a platform admin."""

    async def adjust(
        self,
        org_id: uuid.UUID,
        amount: int,
        description: str,
        user_id: uuid.UUID | None = None,
    ) -> CreditWallet: ...


class AdminRepository(Protocol):
    # -- stats ---------------------------------------------------------------
    async def count_users(self, *, active_only: bool = False) -> int: ...

    async def count_organizations(self) -> int: ...

    # -- organizations ---------------------------------------------------------
    async def list_organizations(
        self, *, search: str, limit: int, offset: int
    ) -> tuple[list[tuple[Organization, int, str | None, str | None]], int]: ...

    async def merge_organizations(
        self, target_id: uuid.UUID, source_ids: list[uuid.UUID]
    ) -> int: ...

    async def list_customer_usage(
        self, *, search: str, sort: str = "joined", limit: int, offset: int
    ) -> tuple[list[CustomerUsageRow], int]:
        """Per-org founder view: who signed up, credits spent."""
        ...

    async def get_organization(self, org_id: uuid.UUID) -> Organization | None: ...

    # -- users -------------------------------------------------------------------
    async def get_user(self, user_id: uuid.UUID) -> User | None: ...

    async def count_user_organizations(self, user_id: uuid.UUID) -> int: ...

    async def list_users(
        self, *, search: str, limit: int, offset: int
    ) -> tuple[list[tuple[User, int]], int]: ...

    # -- credits ----------------------------------------------------------------
    async def list_wallets(
        self, *, search: str, limit: int, offset: int
    ) -> tuple[list[tuple[CreditWallet, str, int]], int]:
        """(wallet, org name, pending hold count) per org, newest first."""
        ...

    # -- generations -------------------------------------------------------------
    async def list_generations(
        self,
        *,
        status: GenerationStatus | None,
        kind: CreditAction | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[Generation, str]], int]:
        """(generation, org name), newest first."""
        ...

    # -- invitations ----------------------------------------------------------------
    async def list_pending_invitations(
        self, *, limit: int, offset: int
    ) -> tuple[list[tuple[Invitation, str, str | None]], int]:
        """(invitation, org name, inviter email), newest first."""
        ...

    async def get_invitation(self, invitation_id: uuid.UUID) -> Invitation | None: ...

    async def delete_invitation(self, invitation: Invitation) -> None: ...

    async def refresh(self, instance: object) -> None:
        """Re-load an entity whose server-generated columns (e.g. updated_at)
        were expired by a flush, so it can be read without sync lazy IO."""
        ...

    # -- audit log -------------------------------------------------------------------
    async def add_audit_entry(self, entry: AdminAuditEntry) -> None: ...

    async def list_audit_log(
        self, *, limit: int, offset: int
    ) -> tuple[list[tuple[AdminAuditEntry, User | None]], int]:
        """(entry, actor user if still present), newest first."""
        ...

    # -- analytics ----------------------------------------------------------------
    async def get_analytics(self) -> Analytics:
        """Aggregated platform-wide analytics for the admin overview dashboard."""
        ...
