"""Credit usage reporting (CQRS-lite read side).

Kept out of `CreditEngine` deliberately: the engine is cohesive around the
wallet lock/settle protocol; this is a pure read with different dependencies.

"Spent" = CAPTURED reservations, the same definition as the platform-admin
org rollup, bucketed by reservation `created_at` in UTC calendar months (the
same window as the monthly allowance and member limits). Pending, released,
and expired holds are excluded; a late capture after expiry ends CAPTURED and
therefore counts once.
"""

import uuid
from datetime import UTC, datetime

from app.domains.credits.application.dtos import ActorUsage, UsageAction, UsageRow
from app.domains.credits.application.ports import MemberLimitRepository, UsageReadRepository


def period_window(period: str) -> tuple[datetime, datetime]:
    """'YYYY-MM' -> [first instant of that UTC month, first of the next)."""
    year, month = int(period[:4]), int(period[5:7])
    start = datetime(year, month, 1, tzinfo=UTC)
    end = (
        datetime(year + 1, 1, 1, tzinfo=UTC)
        if month == 12
        else datetime(year, month + 1, 1, tzinfo=UTC)
    )
    return start, end


def current_period(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m")


def aggregate_rows(
    rows: list[UsageRow], limits: dict[uuid.UUID, int]
) -> tuple[list[ActorUsage], int]:
    """Group action rows per actor, ordered by credits spent (desc).

    Pure so it unit-tests without a database. Returns (actors, total_credits).
    """
    actors: dict[tuple[uuid.UUID | None, uuid.UUID | None], ActorUsage] = {}
    for row in rows:
        key = (row.user_id, row.api_key_id)
        actor = actors.get(key)
        if actor is None:
            actor = ActorUsage(
                user_id=row.user_id,
                user_email=row.user_email,
                user_name=row.user_name,
                api_key_id=row.api_key_id,
                api_key_name=row.api_key_name,
                credits=0,
                count=0,
                limit=limits.get(row.user_id) if row.user_id else None,
            )
            actors[key] = actor
        actor.credits += row.credits
        actor.count += row.count
        actor.actions.append(UsageAction(action=row.action, count=row.count, credits=row.credits))
    ordered = sorted(actors.values(), key=lambda a: a.credits, reverse=True)
    for actor in ordered:
        actor.actions.sort(key=lambda a: a.credits, reverse=True)
    return ordered, sum(a.credits for a in ordered)


class CreditUsageQueries:
    def __init__(self, usage: UsageReadRepository, limits: MemberLimitRepository) -> None:
        self.usage = usage
        self.limits = limits

    async def usage_for_period(
        self, org_id: uuid.UUID, period: str, *, limit: int, offset: int
    ) -> tuple[list[ActorUsage], int, int]:
        """(page of actors ordered by credits desc, total_actors, total_credits)."""
        start, end = period_window(period)
        rows = await self.usage.usage_by_actor(org_id, start, end)
        limit_rows = await self.limits.list_with_usage(org_id, since=start)
        limits = {lim.user_id: lim.monthly_limit for lim, _, _ in limit_rows}
        actors, total_credits = aggregate_rows(rows, limits)
        return actors[offset : offset + limit], len(actors), total_credits
