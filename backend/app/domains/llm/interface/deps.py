"""LLM composition root."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.credits.interface.deps import build_credit_engine
from app.domains.llm.application.use_cases import FinalizeLlmCall, StartLlmCall
from app.domains.llm.infrastructure.providers import DispatchingLlmGateway
from app.domains.llm.infrastructure.repositories import SqlAlchemyLlmCallRepository

DB = Annotated[AsyncSession, Depends(get_db)]

_gateway = DispatchingLlmGateway()


def get_llm_call_repository(db: DB) -> SqlAlchemyLlmCallRepository:
    return SqlAlchemyLlmCallRepository(db)


def get_start_llm_call(db: DB) -> StartLlmCall:
    return StartLlmCall(SqlAlchemyLlmCallRepository(db), build_credit_engine(db), _gateway)


def get_finalize_llm_call(db: DB) -> FinalizeLlmCall:
    return FinalizeLlmCall(SqlAlchemyLlmCallRepository(db), build_credit_engine(db))


def get_llm_gateway() -> DispatchingLlmGateway:
    """Provider gateway for other slices (cross-slice imports go through deps only).

    Satisfies structural ports like blog's DraftLlm — no credits/persistence attached;
    callers own metering and storage.
    """
    return _gateway
