"""RFC 9457 envelope shape tests: AppError rendering, validation flattening,
and the catch-all's no-leak guarantee."""

import pytest_asyncio
from fastapi import APIRouter, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field, field_validator

from app.core.error_handling import field_key, friendly_field_message
from app.core.exceptions import RateLimited
from app.domains.auth.domain import InvalidCredentials
from app.domains.credits.domain.errors import InsufficientCredits
from app.main import app

# Throwaway routes exercising each handler path without touching real slices.
_router = APIRouter(prefix="/_test")


class _Payload(BaseModel):
    email: str
    count: int


class _Profile(BaseModel):
    handle: str = Field(min_length=3)
    age: int = Field(ge=13)

    @field_validator("handle")
    @classmethod
    def _no_spaces(cls, v: str) -> str:
        if " " in v:
            raise ValueError("Handles can't contain spaces.")
        return v


@_router.get("/app-error")
async def _app_error():
    raise InvalidCredentials("Invalid email or password.")


@_router.get("/boom")
async def _boom():
    raise RuntimeError("secret internal detail")


@_router.post("/validate")
async def _validate(payload: _Payload):
    return payload


@_router.post("/profile")
async def _profile(payload: _Profile):
    return payload


@_router.get("/params")
async def _params():
    raise InsufficientCredits("dev text", params={"required": 5, "available": 2, "email": "x@y"})


@_router.get("/rate-limited")
async def _rate_limited():
    raise RateLimited("slow down", retry_after=7)


@_router.get("/http-401")
async def _http_401():
    raise HTTPException(status_code=401, detail="Invalid webhook signature.")


app.include_router(_router, prefix="/api")


async def test_app_error_renders_problem_json(client):
    res = await client.get("/api/_test/app-error")
    assert res.status_code == 401
    assert res.headers["content-type"].startswith("application/problem+json")
    body = res.json()
    assert body["code"] == "ERR_AUTH_001"
    assert body["status"] == 401
    assert body["title"] == "Invalid credentials"
    assert body["detail"] == "Invalid email or password."
    # The correlation id is in the body AND the header, and they agree.
    assert body["instance"] == res.headers["x-request-id"]


async def test_validation_errors_flatten_to_fields(client):
    res = await client.post("/api/_test/validate", json={"email": "x"})
    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "ERR_VAL_001"
    assert "count" in body["fields"]  # missing field surfaced for form binding


@pytest_asyncio.fixture
async def tolerant_client():
    """Starlette re-raises unhandled exceptions after responding; don't let
    that propagation fail the test — we're asserting on the response."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_unhandled_exception_never_leaks(tolerant_client):
    res = await tolerant_client.get("/api/_test/boom")
    assert res.status_code == 500
    body = res.json()
    assert body["code"] == "ERR_SRV_001"
    assert "secret internal detail" not in res.text
    assert "RuntimeError" not in res.text
    assert body["instance"]  # support can still find the traceback by reference


async def test_request_id_round_trip(client):
    """A proxy-supplied X-Request-ID is honored end to end."""
    res = await client.get("/api/health", headers={"X-Request-ID": "proxy-abc-123"})
    assert res.headers["x-request-id"] == "proxy-abc-123"


async def test_params_cross_the_wire_and_undeclared_ones_are_dropped(client):
    res = await client.get("/api/_test/params")
    body = res.json()
    assert body["code"] == "ERR_CRD_001"
    # Declared in errors.toml -> sent; `email` isn't declared -> never leaks.
    assert body["params"] == {"required": 5, "available": 2}


async def test_non_retryable_by_default(client):
    body = (await client.get("/api/_test/app-error")).json()
    assert body["retryable"] is False
    assert "retry_after_ms" not in body
    assert "params" not in body


async def test_rate_limited_is_retryable_with_hint(client):
    res = await client.get("/api/_test/rate-limited")
    assert res.status_code == 429
    assert res.headers["retry-after"] == "7"
    body = res.json()
    assert body["retryable"] is True
    assert body["retry_after_ms"] == 7000


async def test_bare_http_exception_code_matches_status(client):
    res = await client.get("/api/_test/http-401")
    assert res.status_code == 401
    body = res.json()
    assert body["code"] == "ERR_AUTH_003"  # was ERR_REQ_001 (a 400 code) before
    assert body["status"] == 401


async def test_unknown_route_is_not_found(client):
    body = (await client.get("/api/_test/does-not-exist")).json()
    assert body["code"] == "ERR_REQ_002"


async def test_validation_messages_are_user_facing(client):
    res = await client.post("/api/_test/profile", json={"handle": "a b", "age": 5})
    fields = res.json()["fields"]
    assert fields == {
        "handle": "Handles can't contain spaces.",  # "Value error, " prefix stripped
        "age": "Enter a value at least 13.",
    }
    res = await client.post("/api/_test/profile", json={"handle": "ab"})
    fields = res.json()["fields"]
    assert fields["handle"] == "Use at least 3 characters."
    assert fields["age"] == "This field is required."


async def test_malformed_json_is_a_form_level_error(client):
    res = await client.post(
        "/api/_test/profile", content="{not json", headers={"content-type": "application/json"}
    )
    assert res.status_code == 422
    assert res.json()["fields"] == {"__root__": "The request couldn't be read."}


def test_field_key_drops_transport_prefix():
    assert field_key(("body", "members", 0, "email")) == "members.0.email"
    assert field_key(("query", "limit")) == "limit"
    assert field_key(("body",)) == "__root__"


def test_friendly_messages_never_echo_pydantic_internals():
    cases = [
        ({"type": "missing", "msg": "Field required"}, "This field is required."),
        (
            {"type": "value_error", "msg": "value is not a valid email address: no @"},
            "Enter a valid email address.",
        ),
        ({"type": "string_too_long", "ctx": {"max_length": 1}}, "Use at most 1 character."),
        (
            {"type": "int_parsing", "msg": "Input should be a valid integer"},
            "Enter a whole number.",
        ),
        (
            {"type": "literal_error", "ctx": {"expected": "'a' or 'b'"}},
            "Choose one of the available options.",
        ),
        (
            {"type": "url_scheme", "msg": "URL scheme should be 'http'"},
            "Enter a valid link, starting with https://.",
        ),
        (
            {"type": "some_future_type", "msg": "Input should be a weird thing"},
            "This value isn't valid.",
        ),
    ]
    for err, expected in cases:
        assert friendly_field_message(err) == expected
