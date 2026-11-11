"""Admin API schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.policy import ADMIN_CREDIT_NOTE_MAX_LENGTH
from app.domains.credits.domain import CREDIT_PACKS, CreditAction
from app.domains.generations.domain import GenerationStatus
from app.domains.organizations.domain import Role

_BASE_CREDIT_PRICE_CENTS = max(spec.price_cents // spec.credits for spec in CREDIT_PACKS.values())


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


class AdminStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_users: int
    active_users: int
    total_organizations: int


class TimeseriesPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: str
    count: int


class CategoryCountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    count: int


class TopCustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    value: int


class CreditSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_balance: int
    total_pending_holds: int
    total_credits_captured: int


class CommercialSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organizations_with_billing_account: int
    organizations_with_wallet: int
    negative_wallets: int
    zero_balance_wallets: int
    low_balance_wallets: int
    low_balance_threshold: int


class OperationsSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pending_invitations: int
    expired_invitations: int
    open_privacy_requests: int
    overdue_privacy_requests: int
    privacy_requests_due_soon: int
    stale_pending_generations: int
    expired_credit_holds: int


class SecuritySummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    superusers: int
    email_verified_users: int
    unverified_users: int
    email_suppressed_users: int
    active_api_keys: int
    api_keys_used_30d: int
    stale_api_keys: int
    unused_api_keys: int


class AdminAnalyticsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_signups: list[TimeseriesPointOut]
    org_signups: list[TimeseriesPointOut]
    credits_spent_daily: list[TimeseriesPointOut]
    generations_by_status: list[CategoryCountOut]
    generations_by_kind: list[CategoryCountOut]
    top_customers_by_credits: list[TopCustomerOut]
    credit_summary: CreditSummaryOut
    commercial_summary: CommercialSummaryOut
    operations_summary: OperationsSummaryOut
    security_summary: SecuritySummaryOut
    recent_admin_actions: list[CategoryCountOut]


class AdminCustomerUsageOut(BaseModel):
    """Per-org founder view: who has an account and how many credits they spent."""

    organization_id: uuid.UUID
    organization_name: str
    organization_slug: str
    created_at: datetime
    suspended_at: datetime | None
    member_count: int
    owner_email: str | None
    owner_name: str | None
    credits_spent: int
    credit_balance: int | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dollars_spent_cents(self) -> int:
        return self.credits_spent * _BASE_CREDIT_PRICE_CENTS

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dollar_balance_cents(self) -> int | None:
        if self.credit_balance is None:
            return None
        return self.credit_balance * _BASE_CREDIT_PRICE_CENTS


class AdminOrgOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime
    suspended_at: datetime | None
    member_count: int
    owner_email: str | None = None
    owner_name: str | None = None


class AdminOrgSuspensionOut(BaseModel):
    id: uuid.UUID
    suspended_at: datetime | None


class AdminOrgMemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    name: str
    role: Role
    is_active: bool
    joined_at: datetime


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    organization_count: int


class ImpersonationOut(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 — OAuth2 scheme name, not a secret
    user_id: uuid.UUID
    email: str
    name: str


class AdminWalletOut(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    balance: int
    allowance_period: str | None
    pending_holds: int
    updated_at: datetime


class CreditAdjustRequest(BaseModel):
    amount: int = Field(ge=-1_000_000, le=1_000_000)
    description: str = Field(min_length=1, max_length=ADMIN_CREDIT_NOTE_MAX_LENGTH)


class AdminGenerationOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str
    user_id: uuid.UUID | None
    kind: CreditAction
    model: str
    status: GenerationStatus
    prompt: str
    error: str | None
    credits_cost: int
    created_at: datetime
    completed_at: datetime | None


class AdminInvitationOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str
    email: str
    role: Role
    invited_by_email: str | None
    expires_at: datetime
    created_at: datetime


class AdminAuditOut(BaseModel):
    id: uuid.UUID
    actor_email: str | None
    actor_name: str | None
    action: str
    target_type: str
    target_id: uuid.UUID | None
    meta: dict
    created_at: datetime


class MergeOrgsRequest(BaseModel):
    target_id: uuid.UUID
    source_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)


class MergeOrgsOut(BaseModel):
    target_id: uuid.UUID
    merged_count: int
    members_moved: int
