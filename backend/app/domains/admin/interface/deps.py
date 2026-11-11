"""Admin composition root + the superuser gate."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.admin.application import use_cases as uc
from app.domains.admin.domain import NotSuperuser
from app.domains.admin.infrastructure.repositories import SqlAlchemyAdminRepository
from app.domains.auth.domain import User
from app.domains.auth.infrastructure.repositories import SqlAlchemyRefreshTokenRepository
from app.domains.auth.infrastructure.security import JwtTokenService
from app.domains.auth.interface.deps import CurrentUser
from app.domains.credits.interface.deps import build_credit_engine

DB = Annotated[AsyncSession, Depends(get_db)]

_tokens = JwtTokenService()


async def get_current_superuser(user: CurrentUser) -> User:
    if not user.is_superuser:
        raise NotSuperuser("Superuser access required.")
    return user


CurrentSuperuser = Annotated[User, Depends(get_current_superuser)]


def get_admin_repository(db: DB) -> SqlAlchemyAdminRepository:
    return SqlAlchemyAdminRepository(db)


def get_platform_stats(db: DB) -> uc.GetPlatformStats:
    return uc.GetPlatformStats(SqlAlchemyAdminRepository(db))


def get_analytics(db: DB) -> uc.GetAnalytics:
    return uc.GetAnalytics(SqlAlchemyAdminRepository(db))


def get_set_user_active(db: DB) -> uc.SetUserActive:
    return uc.SetUserActive(SqlAlchemyAdminRepository(db), SqlAlchemyRefreshTokenRepository(db))


def get_signout_user_everywhere(db: DB) -> uc.SignOutUserEverywhere:
    return uc.SignOutUserEverywhere(
        SqlAlchemyAdminRepository(db), SqlAlchemyRefreshTokenRepository(db)
    )


def get_impersonate_user(db: DB) -> uc.ImpersonateUser:
    return uc.ImpersonateUser(SqlAlchemyAdminRepository(db), _tokens)


def get_set_org_suspended(db: DB) -> uc.SetOrgSuspended:
    return uc.SetOrgSuspended(SqlAlchemyAdminRepository(db))


def get_adjust_org_credits(db: DB) -> uc.AdjustOrgCredits:
    return uc.AdjustOrgCredits(SqlAlchemyAdminRepository(db), build_credit_engine(db))


def get_revoke_invitation(db: DB) -> uc.RevokeInvitationAdmin:
    return uc.RevokeInvitationAdmin(SqlAlchemyAdminRepository(db))


def get_merge_organizations(db: DB) -> uc.MergeOrganizations:
    return uc.MergeOrganizations(SqlAlchemyAdminRepository(db))
