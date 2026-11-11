"""HTTP schemas for the consent endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.domains.consents.domain import ConsentEvent


class ConsentIn(BaseModel):
    analytics: bool
    policy_version: str = Field(min_length=1, max_length=32)


class ConsentOut(BaseModel):
    analytics: bool
    policy_version: str
    recorded_at: datetime

    @classmethod
    def from_entity(cls, event: ConsentEvent) -> "ConsentOut":
        return cls(
            analytics=event.analytics,
            policy_version=event.policy_version,
            recorded_at=event.created_at,
        )
