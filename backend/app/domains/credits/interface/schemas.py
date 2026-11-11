"""Credits API schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domains.credits.domain import CreditAction, ReservationStatus, TransactionType


class ActionCostOut(BaseModel):
    action: CreditAction
    name: str
    cost: int


class ReservationOut(BaseModel):
    id: uuid.UUID
    action: CreditAction
    amount: int
    status: ReservationStatus
    reference: str | None
    expires_at: datetime
    created_at: datetime


class WalletOut(BaseModel):
    balance: int
    reserved: int  # sum of open holds
    monthly_allowance: int
    allowance_period: str | None
    pending_holds: list[ReservationOut]


class TransactionOut(BaseModel):
    id: uuid.UUID
    type: TransactionType
    action: CreditAction | None
    amount: int
    balance_after: int
    description: str | None
    user_email: str | None
    api_key_name: str | None = None
    reservation_status: ReservationStatus | None
    created_at: datetime


class HistoryOut(BaseModel):
    items: list[TransactionOut]
    total: int


class UsageActionOut(BaseModel):
    action: CreditAction
    count: int
    credits: int


class UsageActorOut(BaseModel):
    user_id: uuid.UUID | None
    user_email: str | None
    user_name: str | None
    api_key_id: uuid.UUID | None
    api_key_name: str | None
    credits: int
    count: int
    limit: int | None
    actions: list[UsageActionOut]


class UsageOut(BaseModel):
    period: str
    items: list[UsageActorOut]
    total_actors: int
    total_credits: int


class MemberLimitIn(BaseModel):
    monthly_limit: int = Field(ge=1)


class MemberLimitOut(BaseModel):
    user_id: uuid.UUID
    email: str | None
    monthly_limit: int
    used_this_period: int
    updated_at: datetime
