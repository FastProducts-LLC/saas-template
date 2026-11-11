"""Credits domain: org-level wallet, reservations (holds), and the ledger.

Credits belong to the *organization* (the tenant), like billing. Every
credit movement is an append-only `CreditTransaction`, so the sum of
transaction amounts always equals the wallet balance and users get a full
audit trail.

The reserve -> capture/release lifecycle exists so metered actions (LLM,
image, video generation) only charge once a result is actually delivered:

  1. ``reserve`` deducts from the available balance and opens a pending
     `CreditReservation` with a TTL.
  2. ``capture`` finalizes the reservation when the result is returned
     (the balance was already deducted at reserve time).
  3. ``release`` (failure) or expiry refunds the hold.

Action costs and the monthly free allowance are flat catalogs here so each
project cloned from this template tunes its own pricing.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domains.credits.domain.errors import InsufficientCredits
from app.domains.credits.domain.value_objects import (
    ActionSpec,
    CreditAction,
    ReservationStatus,
    TransactionType,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(eq=False)
class CreditWallet:
    organization_id: uuid.UUID
    # Available credits. Holds deduct here immediately; releases refund.
    balance: int = 0
    # "YYYY-MM" of the last monthly allowance grant (lazy, on first touch).
    allowance_period: str | None = None
    # "YYYY-MM" of the last low-balance notification (debounce: once/period).
    low_balance_notified_period: str | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def deduct_for_hold(self, spec: ActionSpec) -> None:
        """Reserve-time deduction — the wallet invariant lives here."""
        if self.balance < spec.cost:
            raise InsufficientCredits(
                f"This action needs {spec.cost} credits but only {self.balance} are available.",
                params={"required": spec.cost, "available": max(self.balance, 0)},
            )
        self.balance -= spec.cost

    def refund(self, amount: int) -> None:
        self.balance += amount

    def grant(self, amount: int) -> None:
        self.balance += amount

    def charge_adjustment(self, amount: int) -> None:
        """Late charge — may take the balance negative (service was delivered)."""
        self.balance -= amount


@dataclass(eq=False)
class CreditReservation:
    organization_id: uuid.UUID
    action: CreditAction
    amount: int
    expires_at: datetime
    # Attribution: exactly one of user_id (session user) or api_key_id (API
    # key) is set for metered actions; key usage is never attributed to the
    # key's creator.
    user_id: uuid.UUID | None = None
    api_key_id: uuid.UUID | None = None
    status: ReservationStatus = ReservationStatus.PENDING
    # Free-form pointer to what the hold is for (e.g. a prompt or generation id).
    reference: str | None = None
    finalized_at: datetime | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)

    def _finalize(self, status: ReservationStatus) -> None:
        self.status = status
        self.finalized_at = _utcnow()

    def expire(self) -> None:
        self._finalize(ReservationStatus.EXPIRED)

    def capture(self) -> None:
        self._finalize(ReservationStatus.CAPTURED)

    def release(self) -> None:
        self._finalize(ReservationStatus.RELEASED)


@dataclass(eq=False)
class CreditTransaction:
    """Append-only ledger entry. ``amount`` is the signed effect on the
    available balance; ``balance_after`` snapshots the wallet after it."""

    organization_id: uuid.UUID
    type: TransactionType
    amount: int
    balance_after: int
    action: CreditAction | None = None
    user_id: uuid.UUID | None = None
    api_key_id: uuid.UUID | None = None
    reservation_id: uuid.UUID | None = None
    description: str | None = None
    # External dedup key (e.g. a Stripe checkout session id) — guards grants
    # against webhook redelivery via a partial unique index.
    idempotency_key: str | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(eq=False)
class MemberCreditLimit:
    """Admin-set monthly credit cap for one member of an organization.

    Enforced at reserve time against the member's captured + pending
    reservations in the current UTC calendar month (the same period the
    monthly allowance uses). API-key usage carries no user_id and is exempt —
    the org wallet balance is its ceiling.
    """

    organization_id: uuid.UUID
    user_id: uuid.UUID
    monthly_limit: int
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def set_limit(self, monthly_limit: int) -> None:
        self.monthly_limit = monthly_limit
        self.updated_at = _utcnow()
