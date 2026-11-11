"""Credit engine use cases: reserve -> capture/release, grants, history.

Locking protocol: the wallet row is always locked *before* any reservation
row (wallet -> reservation), so concurrent reserve / release / expiry sweeps
cannot deadlock. The expiry sweep and the monthly allowance are applied
lazily whenever a wallet is touched — correct on its own for any org that
comes back — and a periodic beat task (`tasks.expire_stale_reservations`)
additionally settles orgs with expired holds, so a dormant org whose worker
died mid-action doesn't keep credits held indefinitely.

`CreditEngine` is deliberately one cohesive application service rather than
one class per operation: every operation shares the lazy-settlement protocol
and the ledger-recording invariant, and splitting them would force that
state-machine through module-level helpers.
"""

import logging
import uuid
from datetime import UTC, datetime

from app.domains.credits.application.ports import (
    LedgerRepository,
    LowBalanceNotifier,
    MemberLimitRepository,
    MembershipReader,
    OrgOwnerEmails,
    PlanAllowanceReader,
    ReservationRepository,
    WalletRepository,
)
from app.domains.credits.domain import (
    ACTIONS,
    LOW_BALANCE_FRACTION,
    MONTHLY_ALLOWANCE_CREDITS,
    CreditAction,
    CreditReservation,
    CreditTransaction,
    CreditWallet,
    LimitTargetNotMember,
    MemberCreditLimit,
    MemberCreditLimitExceeded,
    ReservationNotActive,
    ReservationNotFound,
    ReservationStatus,
    TransactionType,
    UnknownAction,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _period_start(now: datetime) -> datetime:
    """First instant of the current UTC calendar month — the member-limit
    accounting period, deliberately the same window as `allowance_period`."""
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class CreditEngine:
    def __init__(
        self,
        wallets: WalletRepository,
        reservations: ReservationRepository,
        ledger: LedgerRepository,
        *,
        notifier: LowBalanceNotifier | None = None,
        owners: OrgOwnerEmails | None = None,
        limits: MemberLimitRepository | None = None,
        plan_allowance_reader: PlanAllowanceReader | None = None,
    ) -> None:
        self.wallets = wallets
        self.reservations = reservations
        self.ledger = ledger
        self.notifier = notifier
        self.owners = owners
        self.limits = limits
        self.plan_allowance_reader = plan_allowance_reader

    # -- wallet lifecycle ------------------------------------------------

    async def _lock_wallet(self, org_id: uuid.UUID) -> CreditWallet:
        """Lock the org wallet, creating it if needed, without settling yet."""
        wallet = await self.wallets.get_for_org_locked(org_id)
        if wallet is None:
            # Racing first touches both see "no wallet": the insert runs in a
            # savepoint so the loser, rejected by unique(organization_id) once
            # the winner commits, recovers by locking the winner's row instead
            # of surfacing an IntegrityError.
            wallet = CreditWallet(organization_id=org_id)
            if not await self.wallets.add_if_absent(wallet):
                wallet = await self.wallets.get_for_org_locked(org_id)
                if wallet is None:  # pragma: no cover — winner rolled back
                    raise RuntimeError(f"Could not create or lock wallet for org {org_id}")
        return wallet

    async def _get_wallet_locked(self, org_id: uuid.UUID) -> CreditWallet:
        wallet = await self._lock_wallet(org_id)
        await self._expire_stale_holds(wallet)
        await self._apply_monthly_allowance(wallet)
        return wallet

    async def _expire_stale_holds(self, wallet: CreditWallet) -> None:
        stale = await self.reservations.list_stale_pending(wallet.organization_id, _now())
        for reservation in stale:
            reservation.expire()
            wallet.refund(reservation.amount)
            self._record(
                wallet,
                type=TransactionType.EXPIRE,
                amount=reservation.amount,
                action=reservation.action,
                user_id=reservation.user_id,
                api_key_id=reservation.api_key_id,
                reservation_id=reservation.id,
                description="Hold expired — credits returned",
            )

    async def _apply_monthly_allowance(self, wallet: CreditWallet) -> None:
        period = _now().strftime("%Y-%m")
        if wallet.allowance_period == period:
            return
        allowance = MONTHLY_ALLOWANCE_CREDITS
        if self.plan_allowance_reader is not None:
            plan_allowance = await self.plan_allowance_reader.monthly_allowance_for(
                wallet.organization_id
            )
            if plan_allowance is not None:
                allowance = plan_allowance
        wallet.allowance_period = period
        # New period — let the low-balance heads-up fire again this month.
        wallet.low_balance_notified_period = None
        if allowance > 0:
            wallet.grant(allowance)
            self._record(
                wallet,
                type=TransactionType.GRANT,
                amount=allowance,
                description=f"Monthly allowance ({period})",
            )

    def _record(
        self,
        wallet: CreditWallet,
        *,
        type: TransactionType,
        amount: int,
        action: CreditAction | None = None,
        user_id: uuid.UUID | None = None,
        api_key_id: uuid.UUID | None = None,
        reservation_id: uuid.UUID | None = None,
        description: str | None = None,
        idempotency_key: str | None = None,
    ) -> CreditTransaction:
        tx = CreditTransaction(
            organization_id=wallet.organization_id,
            user_id=user_id,
            api_key_id=api_key_id,
            reservation_id=reservation_id,
            type=type,
            action=action,
            amount=amount,
            balance_after=wallet.balance,
            description=description,
            idempotency_key=idempotency_key,
        )
        self.ledger.add(tx)
        return tx

    async def settle(self, org_id: uuid.UUID) -> CreditWallet:
        """Settle lazy state only: expire stale holds and apply the monthly
        allowance. Used by the periodic sweep so dormant orgs get their
        refunds without waiting for the next wallet touch. Idempotent."""
        return await self._get_wallet_locked(org_id)

    # -- reserve / capture / release --------------------------------------

    async def reserve(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID | None,
        action: CreditAction,
        reference: str | None = None,
        *,
        api_key_id: uuid.UUID | None = None,
    ) -> CreditReservation:
        """Hold credits for an action. Deducts the available balance now;
        `capture` finalizes the charge, `release` refunds it.

        Attribution: pass the session user's id OR the API key's id (never the
        key creator's user id) — both propagate to the reservation and every
        ledger row it produces."""
        spec = ACTIONS.get(action)
        if spec is None:
            raise UnknownAction(f"No credit cost configured for action '{action}'.")
        wallet = await self._get_wallet_locked(org_id)
        # Under the wallet lock, so concurrent reserves in the org serialize
        # and the usage sum can't race. API-key charges (user_id None) are
        # exempt — the org wallet balance is their ceiling.
        await self._enforce_member_limit(org_id, user_id, spec.cost)
        balance_before = wallet.balance
        wallet.deduct_for_hold(spec)  # raises InsufficientCredits
        reservation = CreditReservation(
            organization_id=org_id,
            user_id=user_id,
            api_key_id=api_key_id,
            action=action,
            amount=spec.cost,
            reference=reference,
            expires_at=_now() + spec.hold_ttl,
        )
        await self.reservations.add(reservation)
        self._record(
            wallet,
            type=TransactionType.HOLD,
            amount=-spec.cost,
            action=action,
            user_id=user_id,
            api_key_id=api_key_id,
            reservation_id=reservation.id,
            description=f"{spec.name} — credits held",
        )
        await self._maybe_notify_low_balance(wallet, balance_before)
        return reservation

    async def _enforce_member_limit(
        self, org_id: uuid.UUID, user_id: uuid.UUID | None, cost: int
    ) -> None:
        if user_id is None or self.limits is None:
            return
        limit = await self.limits.get(org_id, user_id)
        if limit is None:
            return
        used = await self.reservations.sum_active_for_user(
            org_id, user_id, since=_period_start(_now())
        )
        if used + cost > limit.monthly_limit:
            raise MemberCreditLimitExceeded(
                f"Monthly member limit of {limit.monthly_limit} credits reached "
                f"({used} used, {cost} requested)."
            )

    async def _maybe_notify_low_balance(self, wallet: CreditWallet, balance_before: int) -> None:
        """Email the org owners once per allowance period when a hold takes the
        balance from above the low-balance threshold to at-or-below it.

        Best-effort: the period is marked *before* sending and the whole thing
        is wrapped so a mail failure can neither loop nor block the reserve."""
        if self.notifier is None or self.owners is None:
            return
        period = _now().strftime("%Y-%m")
        if wallet.low_balance_notified_period == period:
            return  # already notified this period — debounce
        org_id = wallet.organization_id
        allowance = MONTHLY_ALLOWANCE_CREDITS
        if allowance <= 0:
            return
        threshold = int(allowance * LOW_BALANCE_FRACTION)
        # Crossing-only: from above the threshold to at-or-below it.
        if not (balance_before > threshold and wallet.balance <= threshold):
            return
        # Mark before sending so a mail failure can't loop.
        wallet.low_balance_notified_period = period
        try:
            emails = await self.owners.owner_emails(org_id)
            if emails:
                await self.notifier.notify_low_balance(
                    balance=wallet.balance,
                    allowance=allowance,
                    recipient_emails=emails,
                )
        except Exception:
            logger.exception("Failed to send low-balance notification for org %s", org_id)

    async def capture(self, reservation_id: uuid.UUID) -> CreditReservation:
        """Finalize a hold once the result was delivered. The balance was
        already deducted at reserve time, so this normally only flips state.

        If the hold expired (and was refunded) before the result arrived,
        the charge is re-applied as an adjustment — the service *was*
        delivered — which may take the balance negative."""
        reservation, wallet = await self._get_reservation_and_wallet_locked(reservation_id)
        if reservation.status == ReservationStatus.PENDING:
            reservation.capture()
            return reservation
        if reservation.status == ReservationStatus.EXPIRED:
            logger.warning("Late capture of expired reservation %s — re-charging", reservation_id)
            wallet.charge_adjustment(reservation.amount)
            reservation.capture()
            self._record(
                wallet,
                type=TransactionType.ADJUSTMENT,
                amount=-reservation.amount,
                action=reservation.action,
                user_id=reservation.user_id,
                api_key_id=reservation.api_key_id,
                reservation_id=reservation.id,
                description="Late charge — result delivered after the hold expired",
            )
            return reservation
        raise ReservationNotActive(
            f"Reservation is already {reservation.status.value} and cannot be captured."
        )

    async def release(
        self, reservation_id: uuid.UUID, reason: str | None = None
    ) -> CreditReservation:
        """Refund a hold (the action failed or was cancelled)."""
        reservation, wallet = await self._get_reservation_and_wallet_locked(reservation_id)
        if reservation.status in (ReservationStatus.RELEASED, ReservationStatus.EXPIRED):
            return reservation  # already refunded — idempotent
        if reservation.status == ReservationStatus.CAPTURED:
            raise ReservationNotActive("Reservation was already captured.")
        reservation.release()
        wallet.refund(reservation.amount)
        spec = ACTIONS.get(reservation.action)
        self._record(
            wallet,
            type=TransactionType.RELEASE,
            amount=reservation.amount,
            action=reservation.action,
            user_id=reservation.user_id,
            api_key_id=reservation.api_key_id,
            reservation_id=reservation.id,
            description=reason or f"{spec.name if spec else 'Action'} failed — credits returned",
        )
        return reservation

    async def _get_reservation_and_wallet_locked(
        self, reservation_id: uuid.UUID
    ) -> tuple[CreditReservation, CreditWallet]:
        # Read org_id unlocked first so the wallet is always locked before
        # the reservation (consistent wallet -> reservation lock order).
        peek = await self.reservations.get(reservation_id)
        if peek is None:
            raise ReservationNotFound("Reservation not found.")
        wallet = await self._get_wallet_locked(peek.organization_id)
        reservation = await self.reservations.get_locked(reservation_id)
        if reservation is None:
            raise ReservationNotFound("Reservation not found.")
        return reservation, wallet

    # -- grants & queries --------------------------------------------------

    async def grant(
        self,
        org_id: uuid.UUID,
        amount: int,
        description: str,
        user_id: uuid.UUID | None = None,
        idempotency_key: str | None = None,
    ) -> CreditWallet:
        """Add credits (admin grant, Stripe credit-pack webhook, ...).
        Intentionally not exposed on the org-facing API.

        `idempotency_key` (e.g. a Stripe checkout session id) dedups grants
        driven by at-least-once webhooks. Two defenses make redelivery safe:
        the wallet `FOR UPDATE` lock serializes same-org grants, and once
        locked we re-check `already_granted` so the loser of the race no-ops;
        the partial unique index on the ledger backstops anything that slips
        past (the conflicting insert is rolled back via a savepoint)."""
        wallet = await self._get_wallet_locked(org_id)
        if idempotency_key is not None and await self.already_granted(idempotency_key):
            return wallet  # redelivery — already credited under this key
        wallet.grant(amount)
        tx = CreditTransaction(
            organization_id=wallet.organization_id,
            user_id=user_id,
            reservation_id=None,
            type=TransactionType.GRANT,
            action=None,
            amount=amount,
            balance_after=wallet.balance,
            description=description,
            idempotency_key=idempotency_key,
        )
        if idempotency_key is None:
            self.ledger.add(tx)
        elif not await self.ledger.add_idempotent(tx):
            # The unique index rejected the row: a concurrent grant already
            # wrote this key. Undo the in-memory increment so the wallet isn't
            # double-credited when this transaction commits.
            wallet.charge_adjustment(amount)
        return wallet

    async def top_up_plan_allowance(
        self,
        org_id: uuid.UUID,
        *,
        previous_allowance: int,
        new_allowance: int,
        idempotency_key: str,
    ) -> int:
        wallet = await self._lock_wallet(org_id)
        already_applied = wallet.allowance_period == _now().strftime("%Y-%m")
        await self._expire_stale_holds(wallet)
        await self._apply_monthly_allowance(wallet)
        if new_allowance <= previous_allowance or await self.already_granted(idempotency_key):
            return 0
        amount = new_allowance - previous_allowance if already_applied else 0
        # A zero-value marker also consumes the key when the lazy allowance
        # supplied the full plan amount. Re-subscribing cannot top up again.
        tx = CreditTransaction(
            organization_id=org_id,
            type=TransactionType.GRANT,
            amount=amount,
            balance_after=wallet.balance + amount,
            description=(
                "Plan-upgrade top-up"
                if amount > 0
                else "Plan allowance for this month already applied"
            ),
            idempotency_key=idempotency_key,
        )
        if not await self.ledger.add_idempotent(tx):
            return 0
        wallet.grant(amount)
        return amount

    async def already_granted(self, idempotency_key: str) -> bool:
        """Has a ledger entry with this external key already been written?"""
        return await self.ledger.exists_with_idempotency_key(idempotency_key)

    async def adjust(
        self,
        org_id: uuid.UUID,
        amount: int,
        description: str,
        user_id: uuid.UUID | None = None,
    ) -> CreditWallet:
        """Manual correction by a platform admin: positive adds credits,
        negative removes them (the balance may go negative on purpose).
        Recorded as ADJUSTMENT so it is distinguishable from allowance grants."""
        wallet = await self._get_wallet_locked(org_id)
        if amount >= 0:
            wallet.grant(amount)
        else:
            wallet.charge_adjustment(-amount)
        self._record(
            wallet,
            type=TransactionType.ADJUSTMENT,
            amount=amount,
            user_id=user_id,
            description=description,
        )
        return wallet

    async def summary(self, org_id: uuid.UUID) -> tuple[CreditWallet, list[CreditReservation]]:
        """Wallet (with lazy allowance/expiry settled) and open holds."""
        wallet = await self._get_wallet_locked(org_id)
        pending = await self.reservations.list_pending(org_id)
        return wallet, pending

    async def history(
        self, org_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> tuple[list, int]:
        # Settle lazy state first so history reflects expiries/allowance.
        await self._get_wallet_locked(org_id)
        items = await self.ledger.list_for_org(org_id, limit=limit, offset=offset)
        total = await self.ledger.count_for_org(org_id)
        return items, total


# -- per-member credit limits (admin-managed) --------------------------------


class SetMemberCreditLimit:
    def __init__(self, limits: MemberLimitRepository, members: MembershipReader) -> None:
        self.limits = limits
        self.members = members

    async def execute(
        self, org_id: uuid.UUID, user_id: uuid.UUID, monthly_limit: int
    ) -> MemberCreditLimit:
        if await self.members.get_membership(org_id, user_id) is None:
            raise LimitTargetNotMember("That user is not a member of this organization.")
        limit = await self.limits.get(org_id, user_id)
        if limit is None:
            limit = MemberCreditLimit(
                organization_id=org_id, user_id=user_id, monthly_limit=monthly_limit
            )
            await self.limits.add(limit)
        else:
            limit.set_limit(monthly_limit)
        return limit


class ClearMemberCreditLimit:
    def __init__(self, limits: MemberLimitRepository) -> None:
        self.limits = limits

    async def execute(self, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
        # Idempotent: clearing an absent limit is a no-op.
        await self.limits.remove(org_id, user_id)


class ListMemberCreditLimits:
    def __init__(self, limits: MemberLimitRepository) -> None:
        self.limits = limits

    async def execute(self, org_id: uuid.UUID) -> list[tuple[MemberCreditLimit, str | None, int]]:
        """(limit, member email, credits used this period) per configured limit."""
        return await self.limits.list_with_usage(org_id, since=_period_start(_now()))
