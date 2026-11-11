"""Admin repository: cross-tenant read queries (superuser-only views)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.domains.admin.infrastructure.orm  # noqa: F401
import app.domains.api_keys.infrastructure.orm  # noqa: F401
import app.domains.auth.infrastructure.orm  # noqa: F401
import app.domains.billing.infrastructure.orm  # noqa: F401
import app.domains.credits.infrastructure.orm  # noqa: F401
import app.domains.generations.infrastructure.orm  # noqa: F401
import app.domains.organizations.infrastructure.orm  # noqa: F401
import app.domains.privacy_requests.infrastructure.orm  # noqa: F401
from app.domains.admin.application.ports import (
    Analytics,
    CategoryCount,
    CommercialSummary,
    CreditSummary,
    CustomerUsageRow,
    OperationsSummary,
    SecuritySummary,
    TimeseriesPoint,
    TopCustomer,
)
from app.domains.admin.domain import AdminAuditEntry
from app.domains.api_keys.domain import ApiKey
from app.domains.auth.domain import User
from app.domains.billing.domain import BillingAccount
from app.domains.credits.domain import (
    CreditAction,
    CreditReservation,
    CreditWallet,
    ReservationStatus,
)
from app.domains.generations.domain import Generation, GenerationStatus
from app.domains.organizations.domain import Invitation, Membership, Organization, Role
from app.domains.privacy_requests.domain import PrivacyRequest, PrivacyRequestStatus

_LOW_BALANCE_THRESHOLD = 10


class SqlAlchemyAdminRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _count(self, stmt: Select) -> int:
        return (
            await self.db.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()

    # -- stats -----------------------------------------------------------------

    async def count_users(self, *, active_only: bool = False) -> int:
        stmt = select(func.count()).select_from(User)
        if active_only:
            stmt = stmt.where(User.is_active.is_(True))
        return (await self.db.execute(stmt)).scalar_one()

    async def count_organizations(self) -> int:
        stmt = select(func.count()).select_from(Organization)
        return (await self.db.execute(stmt)).scalar_one()

    # -- organizations -----------------------------------------------------------

    async def list_organizations(
        self, *, search: str, limit: int, offset: int
    ) -> tuple[list[tuple[Organization, int, str | None, str | None]], int]:
        member_counts = (
            select(
                Membership.organization_id,
                func.count().label("member_count"),
            )
            .group_by(Membership.organization_id)
            .subquery()
        )
        owner_rank = (
            select(
                Membership.organization_id,
                Membership.user_id,
                func.row_number()
                .over(
                    partition_by=Membership.organization_id,
                    order_by=Membership.created_at.asc(),
                )
                .label("rn"),
            )
            .where(Membership.role == Role.OWNER)
            .subquery()
        )
        owners = (
            select(
                owner_rank.c.organization_id,
                User.email.label("owner_email"),
                User.first_name.label("owner_first_name"),
                User.last_name.label("owner_last_name"),
            )
            .join(User, User.id == owner_rank.c.user_id)
            .where(owner_rank.c.rn == 1)
            .subquery()
        )
        base = select(Organization)
        if search:
            pattern = f"%{search}%"
            base = base.where(
                or_(Organization.name.ilike(pattern), Organization.slug.ilike(pattern))
            )
        total = await self._count(base)
        stmt = (
            base.add_columns(
                func.coalesce(member_counts.c.member_count, 0),
                owners.c.owner_email,
                owners.c.owner_first_name,
                owners.c.owner_last_name,
            )
            .outerjoin(member_counts, member_counts.c.organization_id == Organization.id)
            .outerjoin(owners, owners.c.organization_id == Organization.id)
            .order_by(Organization.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.db.execute(stmt)).all()
        results: list[tuple[Organization, int, str | None, str | None]] = []
        for org, count, email, first, last in rows:
            owner_name = None
            if first is not None or last is not None:
                owner_name = f"{first or ''} {last or ''}".strip() or None
            results.append((org, count, email, owner_name))
        return results, total

    async def get_organization(self, org_id: uuid.UUID) -> Organization | None:
        return await self.db.get(Organization, org_id)

    async def merge_organizations(self, target_id: uuid.UUID, source_ids: list[uuid.UUID]) -> int:
        """Move all members from source orgs into target, then delete sources.

        Returns the number of members moved.
        """
        from sqlalchemy import text

        moved = 0
        for source_id in source_ids:
            target_user_ids_stmt = select(Membership.user_id).where(
                Membership.organization_id == target_id
            )
            target_user_ids = set((await self.db.execute(target_user_ids_stmt)).scalars().all())

            source_members_stmt = select(Membership).where(Membership.organization_id == source_id)
            source_members = list((await self.db.execute(source_members_stmt)).scalars().all())
            for m in source_members:
                if m.user_id in target_user_ids:
                    await self.db.delete(m)
                else:
                    m.organization_id = target_id
                    moved += 1
                    target_user_ids.add(m.user_id)
            await self.db.flush()

            # Credit wallets: merge balance into target, delete source wallet
            source_wallet = (
                await self.db.execute(
                    select(CreditWallet).where(CreditWallet.organization_id == source_id)
                )
            ).scalar_one_or_none()
            if source_wallet:
                target_wallet = (
                    await self.db.execute(
                        select(CreditWallet).where(CreditWallet.organization_id == target_id)
                    )
                ).scalar_one_or_none()
                if target_wallet:
                    target_wallet.balance += source_wallet.balance
                    await self.db.delete(source_wallet)
                else:
                    source_wallet.organization_id = target_id
                await self.db.flush()

            # Bulk-move all other org-scoped data
            _ORG_TABLES = [
                "api_keys",
                "credit_reservations",
                "credit_transactions",
                "generations",
                "llm_calls",
                "invitations",
            ]
            for tbl in _ORG_TABLES:
                await self.db.execute(
                    text(
                        f"UPDATE {tbl} SET organization_id = :target "  # noqa: S608
                        f"WHERE organization_id = :source"
                    ),
                    {"target": target_id, "source": source_id},
                )

            # Billing accounts: keep target's, delete source's
            await self.db.execute(
                text("DELETE FROM billing_accounts WHERE organization_id = :source"),
                {"source": source_id},
            )

            # Member credit limits: drop source dupes, move the rest
            await self.db.execute(
                text(
                    "DELETE FROM member_credit_limits "
                    "WHERE organization_id = :source AND user_id IN "
                    "(SELECT user_id FROM member_credit_limits "
                    " WHERE organization_id = :target)"
                ),
                {"source": source_id, "target": target_id},
            )
            await self.db.execute(
                text(
                    "UPDATE member_credit_limits "
                    "SET organization_id = :target "
                    "WHERE organization_id = :source"
                ),
                {"target": target_id, "source": source_id},
            )

            # Delete the now-empty source org
            source_org = await self.db.get(Organization, source_id)
            if source_org:
                await self.db.delete(source_org)
            await self.db.flush()

        return moved

    async def list_customer_usage(
        self, *, search: str, sort: str = "joined", limit: int, offset: int
    ) -> tuple[list[CustomerUsageRow], int]:
        """Founder customers view: accounts + credits spent."""
        member_counts = (
            select(
                Membership.organization_id,
                func.count().label("member_count"),
            )
            .group_by(Membership.organization_id)
            .subquery()
        )
        # One owner per org for the "who's got an account" column. If multiple
        # owners exist, pick the earliest membership.
        owner_rank = (
            select(
                Membership.organization_id,
                Membership.user_id,
                func.row_number()
                .over(
                    partition_by=Membership.organization_id,
                    order_by=Membership.created_at.asc(),
                )
                .label("rn"),
            )
            .where(Membership.role == Role.OWNER)
            .subquery()
        )
        owners = (
            select(
                owner_rank.c.organization_id,
                User.email.label("owner_email"),
                User.first_name.label("owner_first_name"),
                User.last_name.label("owner_last_name"),
            )
            .join(User, User.id == owner_rank.c.user_id)
            .where(owner_rank.c.rn == 1)
            .subquery()
        )
        credits_spent = (
            select(
                CreditReservation.organization_id,
                func.coalesce(func.sum(CreditReservation.amount), 0).label("credits_spent"),
            )
            .where(CreditReservation.status == ReservationStatus.CAPTURED)
            .group_by(CreditReservation.organization_id)
            .subquery()
        )

        filters = []
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    Organization.name.ilike(pattern),
                    Organization.slug.ilike(pattern),
                    owners.c.owner_email.ilike(pattern),
                )
            )

        count_stmt = select(Organization.id).outerjoin(
            owners, owners.c.organization_id == Organization.id
        )
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = await self._count(count_stmt)

        stmt = (
            select(
                Organization,
                func.coalesce(member_counts.c.member_count, 0),
                owners.c.owner_email,
                owners.c.owner_first_name,
                owners.c.owner_last_name,
                func.coalesce(credits_spent.c.credits_spent, 0),
                CreditWallet.balance,
            )
            .outerjoin(member_counts, member_counts.c.organization_id == Organization.id)
            .outerjoin(owners, owners.c.organization_id == Organization.id)
            .outerjoin(credits_spent, credits_spent.c.organization_id == Organization.id)
            .outerjoin(CreditWallet, CreditWallet.organization_id == Organization.id)
            .order_by(
                *(
                    (Organization.created_at.desc(),)
                    if sort == "joined"
                    else (
                        func.coalesce(credits_spent.c.credits_spent, 0).desc(),
                        Organization.created_at.desc(),
                    )
                )
            )
            .limit(limit)
            .offset(offset)
        )
        if filters:
            stmt = stmt.where(*filters)

        rows = (await self.db.execute(stmt)).all()
        items: list[CustomerUsageRow] = []
        for (
            org,
            member_count,
            owner_email,
            owner_first,
            owner_last,
            spent,
            balance,
        ) in rows:
            owner_name = None
            if owner_first is not None or owner_last is not None:
                owner_name = f"{owner_first or ''} {owner_last or ''}".strip() or None
            items.append(
                CustomerUsageRow(
                    organization_id=org.id,
                    organization_name=org.name,
                    organization_slug=org.slug,
                    created_at=org.created_at,
                    suspended_at=org.suspended_at,
                    member_count=int(member_count),
                    owner_email=owner_email,
                    owner_name=owner_name,
                    credits_spent=int(spent),
                    credit_balance=int(balance) if balance is not None else None,
                )
            )
        return items, total

    # -- users -------------------------------------------------------------------

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        return await self.db.get(User, user_id)

    async def count_user_organizations(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(Membership).where(Membership.user_id == user_id)
        return (await self.db.execute(stmt)).scalar_one()

    async def list_users(
        self, *, search: str, limit: int, offset: int
    ) -> tuple[list[tuple[User, int]], int]:
        org_counts = (
            select(Membership.user_id, func.count().label("org_count"))
            .group_by(Membership.user_id)
            .subquery()
        )
        base = select(User)
        if search:
            pattern = f"%{search}%"
            base = base.where(
                or_(
                    User.email.ilike(pattern),
                    User.first_name.ilike(pattern),
                    User.last_name.ilike(pattern),
                )
            )
        total = await self._count(base)
        stmt = (
            base.add_columns(func.coalesce(org_counts.c.org_count, 0))
            .outerjoin(org_counts, org_counts.c.user_id == User.id)
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.db.execute(stmt)).all()
        return [(user, count) for user, count in rows], total

    # -- credits ----------------------------------------------------------------

    async def list_wallets(
        self, *, search: str, limit: int, offset: int
    ) -> tuple[list[tuple[CreditWallet, str, int]], int]:
        # NOTE: read-only — balances reflect the last settled state (lazy
        # allowance/expiry runs when a wallet is *touched*, e.g. by adjust).
        pending_holds = (
            select(
                CreditReservation.organization_id,
                func.count().label("hold_count"),
            )
            .where(CreditReservation.status == ReservationStatus.PENDING)
            .group_by(CreditReservation.organization_id)
            .subquery()
        )
        base = select(CreditWallet).join(
            Organization, Organization.id == CreditWallet.organization_id
        )
        if search:
            base = base.where(Organization.name.ilike(f"%{search}%"))
        total = await self._count(base)
        stmt = (
            base.add_columns(
                Organization.name,
                func.coalesce(pending_holds.c.hold_count, 0),
            )
            .outerjoin(
                pending_holds,
                pending_holds.c.organization_id == CreditWallet.organization_id,
            )
            .order_by(CreditWallet.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.db.execute(stmt)).all()
        return [(wallet, org_name, holds) for wallet, org_name, holds in rows], total

    # -- generations -------------------------------------------------------------

    async def list_generations(
        self,
        *,
        status: GenerationStatus | None,
        kind: CreditAction | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[Generation, str]], int]:
        base = select(Generation).join(Organization, Organization.id == Generation.organization_id)
        if status is not None:
            base = base.where(Generation.status == status)
        if kind is not None:
            base = base.where(Generation.kind == kind)
        total = await self._count(base)
        stmt = (
            base.add_columns(Organization.name)
            .order_by(Generation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.db.execute(stmt)).all()
        return [(gen, org_name) for gen, org_name in rows], total

    # -- invitations ----------------------------------------------------------------

    async def list_pending_invitations(
        self, *, limit: int, offset: int
    ) -> tuple[list[tuple[Invitation, str, str | None]], int]:
        base = (
            select(Invitation)
            .join(Organization, Organization.id == Invitation.organization_id)
            .where(Invitation.accepted_at.is_(None))
        )
        total = await self._count(base)
        inviter = User  # joined for the inviter's email; SET NULL keeps it optional
        stmt = (
            base.add_columns(Organization.name, inviter.email)
            .outerjoin(inviter, inviter.id == Invitation.invited_by_id)
            .order_by(Invitation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.db.execute(stmt)).all()
        return [(inv, org_name, inviter_email) for inv, org_name, inviter_email in rows], total

    async def get_invitation(self, invitation_id: uuid.UUID) -> Invitation | None:
        return await self.db.get(Invitation, invitation_id)

    async def delete_invitation(self, invitation: Invitation) -> None:
        await self.db.delete(invitation)

    async def refresh(self, instance: object) -> None:
        await self.db.refresh(instance)

    # -- audit log -------------------------------------------------------------------

    async def add_audit_entry(self, entry: AdminAuditEntry) -> None:
        self.db.add(entry)
        await self.db.flush()

    async def list_audit_log(
        self, *, limit: int, offset: int
    ) -> tuple[list[tuple[AdminAuditEntry, User | None]], int]:
        base = select(AdminAuditEntry)
        total = await self._count(base)
        stmt = (
            base.add_columns(User)
            .outerjoin(User, User.id == AdminAuditEntry.actor_user_id)
            .order_by(AdminAuditEntry.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.db.execute(stmt)).all()
        return [(entry, actor) for entry, actor in rows], total

    # -- analytics -------------------------------------------------------------------

    async def get_analytics(self) -> Analytics:
        """Platform-wide aggregates for the admin overview dashboard."""
        now = datetime.now(UTC)
        cutoff_30d = now - timedelta(days=30)
        cutoff_7d = now - timedelta(days=7)
        api_key_stale_cutoff = now - timedelta(days=90)
        privacy_due_soon = now + timedelta(days=7)
        stale_generation_cutoff = now - timedelta(hours=2)

        # --- time series: daily signups + credits spent (last 30 days) ---
        user_signups = await self._daily_counts(User.created_at, cutoff_30d, now)
        org_signups = await self._daily_counts(Organization.created_at, cutoff_30d, now)
        credits_spent_daily = await self._daily_credit_spend(cutoff_30d, now)

        # --- breakdowns: generations by status / kind (one scan, split in Python) ---
        gen_rows = (
            await self.db.execute(
                select(Generation.status, Generation.kind, func.count().label("cnt"))
                .where(Generation.created_at >= cutoff_30d)
                .group_by(Generation.status, Generation.kind)
            )
        ).all()
        by_status: dict[str, int] = {}
        by_kind: dict[str, int] = {}
        for status, kind, cnt in gen_rows:
            by_status[status.value] = by_status.get(status.value, 0) + int(cnt)
            by_kind[kind.value] = by_kind.get(kind.value, 0) + int(cnt)
        generations_by_status = [
            CategoryCount(label=label, count=count)
            for label, count in sorted(by_status.items(), key=lambda kv: -kv[1])
        ]
        generations_by_kind = [
            CategoryCount(label=label, count=count)
            for label, count in sorted(by_kind.items(), key=lambda kv: -kv[1])
        ]

        # --- top 10 customers by credits spent ---
        # Inner-join from captured reservations: dormant orgs never enter the
        # sort, and no manufactured zero rows need filtering afterwards.
        top_credits_stmt = (
            select(
                Organization.name,
                func.sum(CreditReservation.amount).label("amt"),
            )
            .join(Organization, Organization.id == CreditReservation.organization_id)
            .where(CreditReservation.status == ReservationStatus.CAPTURED)
            .group_by(Organization.id, Organization.name)
            .order_by(func.sum(CreditReservation.amount).desc())
            .limit(10)
        )
        top_credits_rows = (await self.db.execute(top_credits_stmt)).all()
        top_customers_by_credits = [
            TopCustomer(name=name, value=int(amt)) for name, amt in top_credits_rows
        ]

        # --- credit/commercial summaries ---
        summary_row = (
            await self.db.execute(
                select(
                    select(func.coalesce(func.sum(CreditWallet.balance), 0))
                    .select_from(CreditWallet)
                    .scalar_subquery()
                    .label("balance"),
                    func.count()
                    .filter(CreditReservation.status == ReservationStatus.PENDING)
                    .label("pending"),
                    func.coalesce(
                        func.sum(CreditReservation.amount).filter(
                            CreditReservation.status == ReservationStatus.CAPTURED
                        ),
                        0,
                    ).label("captured"),
                ).select_from(CreditReservation)
            )
        ).one()
        commercial_row = (
            await self.db.execute(
                select(
                    select(func.count())
                    .select_from(BillingAccount)
                    .where(BillingAccount.stripe_customer_id.is_not(None))
                    .scalar_subquery()
                    .label("organizations_with_billing_account"),
                    select(func.count())
                    .select_from(CreditWallet)
                    .scalar_subquery()
                    .label("organizations_with_wallet"),
                    select(func.count())
                    .select_from(CreditWallet)
                    .where(CreditWallet.balance < 0)
                    .scalar_subquery()
                    .label("negative_wallets"),
                    select(func.count())
                    .select_from(CreditWallet)
                    .where(CreditWallet.balance == 0)
                    .scalar_subquery()
                    .label("zero_balance_wallets"),
                    select(func.count())
                    .select_from(CreditWallet)
                    .where(
                        CreditWallet.balance > 0,
                        CreditWallet.balance <= _LOW_BALANCE_THRESHOLD,
                    )
                    .scalar_subquery()
                    .label("low_balance_wallets"),
                )
            )
        ).one()

        # --- operational backlog / stuck-work summary ---
        open_privacy_statuses = (
            PrivacyRequestStatus.RECEIVED,
            PrivacyRequestStatus.VERIFIED,
            PrivacyRequestStatus.FORWARDED,
        )
        operations_row = (
            await self.db.execute(
                select(
                    select(func.count())
                    .select_from(Invitation)
                    .where(Invitation.accepted_at.is_(None), Invitation.expires_at >= now)
                    .scalar_subquery()
                    .label("pending_invitations"),
                    select(func.count())
                    .select_from(Invitation)
                    .where(Invitation.accepted_at.is_(None), Invitation.expires_at < now)
                    .scalar_subquery()
                    .label("expired_invitations"),
                    select(func.count())
                    .select_from(PrivacyRequest)
                    .where(PrivacyRequest.status.in_(open_privacy_statuses))
                    .scalar_subquery()
                    .label("open_privacy_requests"),
                    select(func.count())
                    .select_from(PrivacyRequest)
                    .where(
                        PrivacyRequest.status.in_(open_privacy_statuses),
                        PrivacyRequest.deadline_at.is_not(None),
                        PrivacyRequest.deadline_at < now,
                    )
                    .scalar_subquery()
                    .label("overdue_privacy_requests"),
                    select(func.count())
                    .select_from(PrivacyRequest)
                    .where(
                        PrivacyRequest.status.in_(open_privacy_statuses),
                        PrivacyRequest.deadline_at.is_not(None),
                        PrivacyRequest.deadline_at >= now,
                        PrivacyRequest.deadline_at <= privacy_due_soon,
                    )
                    .scalar_subquery()
                    .label("privacy_requests_due_soon"),
                    select(func.count())
                    .select_from(Generation)
                    .where(
                        Generation.status == GenerationStatus.PENDING,
                        Generation.created_at < stale_generation_cutoff,
                    )
                    .scalar_subquery()
                    .label("stale_pending_generations"),
                    select(func.count())
                    .select_from(CreditReservation)
                    .where(
                        CreditReservation.status == ReservationStatus.PENDING,
                        CreditReservation.expires_at < now,
                    )
                    .scalar_subquery()
                    .label("expired_credit_holds"),
                )
            )
        ).one()

        # --- security / access posture summary ---
        user_security_row = (
            await self.db.execute(
                select(
                    func.count().filter(User.is_superuser.is_(True)).label("superusers"),
                    func.count()
                    .filter(User.email_verified_at.is_not(None))
                    .label("email_verified_users"),
                    func.count()
                    .filter(User.is_active.is_(True), User.email_verified_at.is_(None))
                    .label("unverified_users"),
                    func.count()
                    .filter(User.email_suppressed.is_(True))
                    .label("email_suppressed_users"),
                ).select_from(User)
            )
        ).one()
        api_key_security_row = (
            await self.db.execute(
                select(
                    func.count().filter(ApiKey.revoked_at.is_(None)).label("active_api_keys"),
                    func.count()
                    .filter(ApiKey.revoked_at.is_(None), ApiKey.last_used_at >= cutoff_30d)
                    .label("api_keys_used_30d"),
                    func.count()
                    .filter(
                        ApiKey.revoked_at.is_(None),
                        or_(
                            ApiKey.last_used_at < api_key_stale_cutoff,
                            ApiKey.last_used_at.is_(None)
                            & (ApiKey.created_at < api_key_stale_cutoff),
                        ),
                    )
                    .label("stale_api_keys"),
                    func.count()
                    .filter(ApiKey.revoked_at.is_(None), ApiKey.last_used_at.is_(None))
                    .label("unused_api_keys"),
                ).select_from(ApiKey)
            )
        ).one()

        recent_actions_rows = (
            await self.db.execute(
                select(AdminAuditEntry.action, func.count().label("cnt"))
                .where(AdminAuditEntry.created_at >= cutoff_7d)
                .group_by(AdminAuditEntry.action)
                .order_by(func.count().desc(), AdminAuditEntry.action.asc())
                .limit(8)
            )
        ).all()
        recent_admin_actions = [
            CategoryCount(label=action, count=int(cnt)) for action, cnt in recent_actions_rows
        ]

        return Analytics(
            user_signups=user_signups,
            org_signups=org_signups,
            credits_spent_daily=credits_spent_daily,
            generations_by_status=generations_by_status,
            generations_by_kind=generations_by_kind,
            top_customers_by_credits=top_customers_by_credits,
            credit_summary=CreditSummary(
                total_balance=int(summary_row.balance),
                total_pending_holds=int(summary_row.pending),
                total_credits_captured=int(summary_row.captured),
            ),
            commercial_summary=CommercialSummary(
                organizations_with_billing_account=int(
                    commercial_row.organizations_with_billing_account
                ),
                organizations_with_wallet=int(commercial_row.organizations_with_wallet),
                negative_wallets=int(commercial_row.negative_wallets),
                zero_balance_wallets=int(commercial_row.zero_balance_wallets),
                low_balance_wallets=int(commercial_row.low_balance_wallets),
                low_balance_threshold=_LOW_BALANCE_THRESHOLD,
            ),
            operations_summary=OperationsSummary(
                pending_invitations=int(operations_row.pending_invitations),
                expired_invitations=int(operations_row.expired_invitations),
                open_privacy_requests=int(operations_row.open_privacy_requests),
                overdue_privacy_requests=int(operations_row.overdue_privacy_requests),
                privacy_requests_due_soon=int(operations_row.privacy_requests_due_soon),
                stale_pending_generations=int(operations_row.stale_pending_generations),
                expired_credit_holds=int(operations_row.expired_credit_holds),
            ),
            security_summary=SecuritySummary(
                superusers=int(user_security_row.superusers),
                email_verified_users=int(user_security_row.email_verified_users),
                unverified_users=int(user_security_row.unverified_users),
                email_suppressed_users=int(user_security_row.email_suppressed_users),
                active_api_keys=int(api_key_security_row.active_api_keys),
                api_keys_used_30d=int(api_key_security_row.api_keys_used_30d),
                stale_api_keys=int(api_key_security_row.stale_api_keys),
                unused_api_keys=int(api_key_security_row.unused_api_keys),
            ),
            recent_admin_actions=recent_admin_actions,
        )

    async def _daily_counts(
        self, col: object, cutoff: datetime, now: datetime
    ) -> list[TimeseriesPoint]:
        """Day-bucketed row counts for the last 30 days (fills zero days)."""
        stmt = (
            select(
                func.date_trunc("day", col).label("day"),
                func.count().label("cnt"),
            )
            .where(col >= cutoff, col < now)
            .group_by("day")
            .order_by("day")
        )
        rows = {row.day.date().isoformat(): int(row.cnt) for row in (await self.db.execute(stmt))}
        return self._fill_days(rows, cutoff, now)

    async def _daily_credit_spend(self, cutoff: datetime, now: datetime) -> list[TimeseriesPoint]:
        """Day-bucketed captured credit amounts for the last 30 days.

        Bucketed by reservation created_at (there is no captured_at column),
        so a hold captured after midnight graphs on the day it was reserved —
        an acceptable approximation for a trend chart; the summary counters
        remain exact."""
        stmt = (
            select(
                func.date_trunc("day", CreditReservation.created_at).label("day"),
                func.coalesce(func.sum(CreditReservation.amount), 0).label("amt"),
            )
            .where(
                CreditReservation.status == ReservationStatus.CAPTURED,
                CreditReservation.created_at >= cutoff,
                CreditReservation.created_at < now,
            )
            .group_by("day")
            .order_by("day")
        )
        rows = {row.day.date().isoformat(): int(row.amt) for row in (await self.db.execute(stmt))}
        return self._fill_days(rows, cutoff, now)

    @staticmethod
    def _fill_days(rows: dict[str, int], cutoff: datetime, now: datetime) -> list[TimeseriesPoint]:
        points: list[TimeseriesPoint] = []
        day = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        while day <= end:
            iso = day.date().isoformat()
            points.append(TimeseriesPoint(date=iso, count=rows.get(iso, 0)))
            day += timedelta(days=1)
        return points
