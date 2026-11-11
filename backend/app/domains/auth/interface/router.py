"""Auth HTTP endpoints — thin: parse request → use case → serialize."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.policy import (
    RATE_LIMIT_AUTH_CHANGE_PASSWORD,
    RATE_LIMIT_AUTH_FORGOT_PASSWORD,
    RATE_LIMIT_AUTH_LOGIN,
    RATE_LIMIT_AUTH_REFRESH,
    RATE_LIMIT_AUTH_REGISTER,
    RATE_LIMIT_AUTH_RESEND_VERIFICATION,
    RATE_LIMIT_AUTH_RESET_PASSWORD,
    RATE_LIMIT_AUTH_VERIFY_EMAIL,
)
from app.core.ratelimit import limiter
from app.domains.auth.application import use_cases as uc
from app.domains.auth.domain import SessionExpired
from app.domains.auth.interface.deps import (
    CurrentUser,
    NoImpersonation,
    get_change_password,
    get_forgot_password,
    get_login_user,
    get_logout_user,
    get_refresh_session,
    get_register_user,
    get_resend_verification,
    get_reset_password,
    get_update_profile,
    get_verify_email,
)
from app.domains.auth.interface.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegistrationPending,
    ResetPasswordRequest,
    SessionResponse,
    TokenResponse,
    UpdateMeRequest,
    UserOut,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"

# Native apps have no httpOnly cookie jar. Clients that send `X-Client: mobile`
# get the refresh token in the response body instead of a cookie and send it
# back in the request body on refresh/logout. Web keeps the cookie flow — a
# body-visible refresh token would be exposed to page scripts (XSS).
MOBILE_CLIENT_HEADER = "x-client"
MOBILE_CLIENT_VALUE = "mobile"


def _is_mobile_client(request: Request) -> bool:
    return request.headers.get(MOBILE_CLIENT_HEADER, "").lower() == MOBILE_CLIENT_VALUE


def _client_context(request: Request) -> dict:
    """IP + user agent for the audit trail. Same proxy caveat as the rate
    limiter: behind Caddy, uvicorn must run with --forwarded-allow-ips."""
    return {
        "ip": get_remote_address(request),
        "user_agent": (request.headers.get("user-agent") or "")[:256] or None,
    }


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        raw_token,
        max_age=settings.refresh_token_ttl_days * 86400,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


@router.post(
    "/register",
    response_model=UserOut | RegistrationPending,
    status_code=status.HTTP_201_CREATED,
    responses={202: {"model": RegistrationPending}},
)
@limiter.limit(RATE_LIMIT_AUTH_REGISTER)
async def register(
    request: Request,
    response: Response,
    payload: RegisterRequest,
    use_case: Annotated[uc.RegisterUser, Depends(get_register_user)],
):
    user = await use_case.execute(
        email=payload.email,
        password=payload.password,
        password_confirmation=payload.password_confirmation,
        first_name=payload.first_name,
        last_name=payload.last_name,
        terms_accepted=payload.terms_accepted,
        marketing_opt_in=payload.marketing_opt_in,
    )
    if use_case.enumeration_safe:
        # Verify-first signup: one answer whether the account was just
        # created or already existed (SIGNUP_ENUMERATION_PROTECTION).
        response.status_code = status.HTTP_202_ACCEPTED
        return RegistrationPending()
    return user


@router.post("/login", response_model=SessionResponse)
@limiter.limit(RATE_LIMIT_AUTH_LOGIN)
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    use_case: Annotated[uc.LoginUser, Depends(get_login_user)],
):
    user, access_token, refresh_token = await use_case.execute(
        payload.email, payload.password, **_client_context(request)
    )
    if _is_mobile_client(request):
        return SessionResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserOut.model_validate(user),
        )
    _set_refresh_cookie(response, refresh_token)
    return SessionResponse(access_token=access_token, user=UserOut.model_validate(user))


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(RATE_LIMIT_AUTH_REFRESH)
async def refresh(
    request: Request,
    response: Response,
    use_case: Annotated[uc.RefreshSession, Depends(get_refresh_session)],
    payload: RefreshRequest | None = None,
):
    body_token = payload.refresh_token if payload else None
    raw = body_token or request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise SessionExpired("Missing refresh token.")
    access_token, new_refresh = await use_case.execute(raw, **_client_context(request))
    if body_token:
        return TokenResponse(access_token=access_token, refresh_token=new_refresh)
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    use_case: Annotated[uc.LogoutUser, Depends(get_logout_user)],
    payload: RefreshRequest | None = None,
):
    raw = (payload.refresh_token if payload else None) or request.cookies.get(REFRESH_COOKIE)
    if raw:
        await use_case.execute(raw)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: UpdateMeRequest,
    user: CurrentUser,
    use_case: Annotated[uc.UpdateProfile, Depends(get_update_profile)],
):
    """Partial profile update (name, marketing consent, analytics opt-out —
    only provided fields)."""
    return await use_case.execute(
        user,
        first_name=payload.first_name,
        last_name=payload.last_name,
        marketing_opt_in=payload.marketing_opt_in,
        analytics_opt_out=payload.analytics_opt_out,
    )


@router.post("/change-password", response_model=TokenResponse, dependencies=[NoImpersonation])
@limiter.limit(RATE_LIMIT_AUTH_CHANGE_PASSWORD)
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    user: CurrentUser,
    response: Response,
    use_case: Annotated[uc.ChangePassword, Depends(get_change_password)],
):
    """Change password while signed in. Revokes every other session."""
    access_token, new_refresh = await use_case.execute(
        user,
        current_password=payload.current_password,
        password=payload.password,
        password_confirmation=payload.password_confirmation,
        **_client_context(request),
    )
    if _is_mobile_client(request):
        return TokenResponse(access_token=access_token, refresh_token=new_refresh)
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=access_token)


# ── Email verification (account activation) ─────────────────────────


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(RATE_LIMIT_AUTH_VERIFY_EMAIL)
async def verify_email(
    request: Request,
    response: Response,
    payload: VerifyEmailRequest,
    use_case: Annotated[uc.VerifyEmail, Depends(get_verify_email)],
):
    await use_case.execute(payload.token)


@router.post("/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(RATE_LIMIT_AUTH_RESEND_VERIFICATION)
async def resend_verification(
    request: Request,
    response: Response,
    user: CurrentUser,
    use_case: Annotated[uc.ResendVerification, Depends(get_resend_verification)],
):
    await use_case.execute(user)


# ── Password reset ───────────────────────────────────────────────────


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(RATE_LIMIT_AUTH_FORGOT_PASSWORD)
async def forgot_password(
    request: Request,
    response: Response,
    payload: ForgotPasswordRequest,
    use_case: Annotated[uc.ForgotPassword, Depends(get_forgot_password)],
):
    """Always 204 — whether the account exists is never revealed."""
    await use_case.execute(payload.email)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(RATE_LIMIT_AUTH_RESET_PASSWORD)
async def reset_password(
    request: Request,
    response: Response,
    payload: ResetPasswordRequest,
    use_case: Annotated[uc.ResetPassword, Depends(get_reset_password)],
):
    await use_case.execute(
        token=payload.token,
        password=payload.password,
        password_confirmation=payload.password_confirmation,
        **_client_context(request),
    )
