"""Auth transactional email content. Each builder returns (subject, text, html).

Rendering is infrastructure — copy changes never touch use-case logic.
"""

from html import escape

from app.core.config import settings
from app.core.email.layout import render_email
from app.domains.auth.domain import User


def welcome_email(user: User, verify_url: str) -> tuple[str, str, str]:
    """Welcome + account activation in one message (sent right after signup)."""
    subject = f"Welcome to {settings.app_name} — confirm your email"
    text = (
        f"Hi {user.first_name},\n\n"
        f"Welcome to {settings.app_name}! Your account is ready to go.\n\n"
        f"Confirm your email address to activate your account:\n{verify_url}\n\n"
        f"This link expires in {settings.email_verification_ttl_hours} hours."
    )
    html = render_email(
        heading=f"Welcome, {user.first_name}!",
        body_html=(
            f"<p>Thanks for signing up for {escape(settings.app_name)}. "
            f"Your account is ready to go.</p>"
            f"<p>Confirm your email address to activate your account.</p>"
        ),
        cta_label="Confirm email",
        cta_url=verify_url,
        footer_note=(
            f"This link expires in {settings.email_verification_ttl_hours} hours. "
            "If you didn't create this account, you can safely ignore this email."
        ),
    )
    return subject, text, html


def verification_email(user: User, verify_url: str) -> tuple[str, str, str]:
    """Standalone activation email (re-sent on request)."""
    subject = "Verify your email address"
    text = (
        f"Hi {user.first_name},\n\n"
        f"Confirm your email address for {settings.app_name}:\n{verify_url}\n\n"
        f"This link expires in {settings.email_verification_ttl_hours} hours."
    )
    html = render_email(
        heading="Verify your email address",
        body_html=(
            f"<p>Hi {escape(user.first_name)},</p>"
            f"<p>Confirm this email address to activate your "
            f"{escape(settings.app_name)} account.</p>"
        ),
        cta_label="Verify email",
        cta_url=verify_url,
        footer_note=(
            f"This link expires in {settings.email_verification_ttl_hours} hours. "
            "If you didn't request this, you can safely ignore this email."
        ),
    )
    return subject, text, html


def password_reset_email(user: User, reset_url: str) -> tuple[str, str, str]:
    subject = "Reset your password"
    text = (
        f"Hi {user.first_name},\n\n"
        f"We received a request to reset your {settings.app_name} password.\n\n"
        f"Choose a new password:\n{reset_url}\n\n"
        f"This link expires in {settings.password_reset_ttl_minutes} minutes. "
        "If you didn't request this, you can safely ignore this email — "
        "your password is unchanged."
    )
    html = render_email(
        heading="Reset your password",
        body_html=(
            f"<p>Hi {escape(user.first_name)},</p>"
            f"<p>We received a request to reset your "
            f"{escape(settings.app_name)} password.</p>"
        ),
        cta_label="Choose a new password",
        cta_url=reset_url,
        footer_note=(
            f"This link expires in {settings.password_reset_ttl_minutes} minutes. "
            "If you didn't request this, you can safely ignore this email — "
            "your password is unchanged."
        ),
    )
    return subject, text, html


def password_changed_email(user: User, reset_url: str) -> tuple[str, str, str]:
    """Security notice sent after any successful password change or reset."""
    subject = f"Your {settings.app_name} password was changed"
    warning = (
        "If this was you, no action is needed. If it wasn't, reset your "
        "password right away — every other session has already been signed out."
    )
    text = (
        f"Hi {user.first_name},\n\n"
        f"The password for your {settings.app_name} account was just changed.\n\n"
        f"{warning}\n\n"
        f"Reset your password:\n{reset_url}"
    )
    html = render_email(
        heading="Your password was changed",
        body_html=(
            f"<p>Hi {escape(user.first_name)},</p>"
            f"<p>The password for your {escape(settings.app_name)} account "
            f"was just changed.</p>"
        ),
        cta_label="This wasn't me — reset password",
        cta_url=reset_url,
        footer_note=warning,
    )
    return subject, text, html


def account_exists_email(user: User, login_url: str, reset_url: str) -> tuple[str, str, str]:
    """Verify-first signup: sent to the owner when someone tries to register
    an address that already has an account. The signup page itself reveals
    nothing, so this is how a forgetful owner finds out."""
    subject = f"You already have a {settings.app_name} account"
    note = (
        "If this wasn't you, no action is needed — nothing about your account "
        "has changed, and no new account was created."
    )
    text = (
        f"Hi {user.first_name},\n\n"
        f"Someone just tried to sign up for {settings.app_name} with this email "
        f"address, but it already has an account.\n\n"
        f"Sign in:\n{login_url}\n\n"
        f"Forgot your password? Reset it:\n{reset_url}\n\n"
        f"{note}"
    )
    html = render_email(
        heading="You already have an account",
        body_html=(
            f"<p>Hi {escape(user.first_name)},</p>"
            f"<p>Someone just tried to sign up for {escape(settings.app_name)} "
            f"with this email address, but it already has an account.</p>"
            f'<p>Forgot your password? <a href="{escape(reset_url)}">Reset it</a>.</p>'
        ),
        cta_label="Sign in",
        cta_url=login_url,
        footer_note=note,
    )
    return subject, text, html
