"""Superuser-only platform revenue reporting."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.domains.admin.interface.deps import CurrentSuperuser
from app.domains.billing.application.revenue import GetRevenue
from app.domains.billing.interface.admin_schemas import RevenueOut
from app.domains.billing.interface.deps import get_revenue

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/revenue", response_model=RevenueOut)
async def revenue(
    user: CurrentSuperuser,
    query: Annotated[GetRevenue, Depends(get_revenue)],
) -> RevenueOut:
    return RevenueOut.model_validate(await query.execute())
