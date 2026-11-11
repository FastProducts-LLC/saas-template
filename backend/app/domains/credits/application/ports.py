"""Credits application ports."""

import uuid
from datetime import datetime
from typing import Protocol

from app.domains.credits.application.dtos import UsageRow
from app.domains.credits.domain import (
    CreditReservation,
    CreditTransaction,
    CreditWallet,
    MemberCreditLimit,
    ReservationStatus,
)


class WalletRepository(Protocol):
    async def get_for_org_locked(self, org_id: uuid.UUID) -> CreditWallet | None:
        """Lock the wallet row for the rest of the transaction. All balance
        mutations must go through this to serialize concurrent holds."""
        ...

    async def add_if_absent(self, wallet: CreditWallet) -> bool:
        """Insert the wallet inside a savepoint. Returns False when another
        transaction won the unique(organization_id) race — the caller should
        re-fetch the winner's row instead of failing."""
        ...


class ReservationRepository(Protocol):
    async def get(self, reservation_id: uuid.UUID) -> CreditReservation | None: ...

    async def get_locked(self, reservation_id: uuid.UUID) -> CreditReservation | None: ...

    async def list_stale_pending(
        self, org_id: uuid.UUID, now: datetime
    ) -> list[CreditReservation]: ...

    async def list_orgs_with_stale_pending(
        self, now: datetime, limit: int = 500
    ) -> list[uuid.UUID]: ...

    async def list_pending(self, org_id: uuid.UUID) -> list[CreditReservation]: ...

    async def add(self, reservation: CreditReservation) -> None: ...

    async def sum_active_for_user(
        self, org_id: uuid.UUID, user_id: uuid.UUID, since: datetime
    ) -> int:
        """Sum of PENDING + CAPTURED reservation amounts this user opened in
        the org since `since` — the member-limit usage counter."""
        ...


class LedgerRepository(Protocol):
    def add(self, tx: CreditTransaction) -> None: ...

    async def add_idempotent(self, tx: CreditTransaction) -> bool:
        """Add a transaction and flush it inside a savepoint. Return True if it
        was written, or False if its `idempotency_key` collided with an
        existing row (the unique-violation backstop for webhook redelivery) —
        in which case the savepoint is rolled back so no partial state leaks."""
        ...

    async def exists_with_idempotency_key(self, key: str) -> bool: ...

    async def list_for_org(
        self, org_id: uuid.UUID, limit: int, offset: int
    ) -> list[tuple[CreditTransaction, str | None, str | None, ReservationStatus | None]]:
        """Rows of (transaction, user_email, api_key_name, reservation_status)."""
        ...

    async def count_for_org(self, org_id: uuid.UUID) -> int: ...


class MemberLimitRepository(Protocol):
    async def get(self, org_id: uuid.UUID, user_id: uuid.UUID) -> MemberCreditLimit | None: ...

    async def add(self, limit: MemberCreditLimit) -> None: ...

    async def remove(self, org_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...

    async def list_with_usage(
        self, org_id: uuid.UUID, since: datetime
    ) -> list[tuple[MemberCreditLimit, str | None, int]]:
        """All limits for the org with the member's email and their captured +
        pending usage since `since`, for the admin limits endpoint."""
        ...


class UsageReadRepository(Protocol):
    async def usage_by_actor(
        self, org_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[UsageRow]:
        """CAPTURED reservations in [start, end) grouped by
        (user_id, api_key_id, action), with user email/name and key name."""
        ...


class MembershipReader(Protocol):
    """Minimal slice of the organizations repo the limit use cases need —
    satisfied structurally by `SqlAlchemyOrgRepository`."""

    async def get_membership(self, org_id: uuid.UUID, user_id: uuid.UUID) -> object | None: ...


class LowBalanceNotifier(Protocol):
    async def notify_low_balance(
        self, *, balance: int, allowance: int, recipient_emails: list[str]
    ) -> None: ...


class OrgOwnerEmails(Protocol):
    async def owner_emails(self, org_id: uuid.UUID) -> list[str]: ...


class PlanAllowanceReader(Protocol):
    async def monthly_allowance_for(self, org_id: uuid.UUID) -> int | None: ...
