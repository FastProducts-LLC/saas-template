"""Email-domain helpers shared across slices (e.g. company-domain claiming)."""

from __future__ import annotations

PUBLIC_EMAIL_DOMAINS = frozenset(
    {
        # Shared consumer mailbox providers
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.uk",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "msn.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "pm.me",
        "gmx.com",
        "gmx.net",
        "zoho.com",
        "mail.com",
        "yandex.com",
        "fastmail.com",
        "hey.com",
        "tutanota.com",
        "duck.com",
        # RFC 2606 / 6761 reserved — used heavily in tests & docs; never claimable
        "example.com",
        "example.net",
        "example.org",
        "example.edu",
        "invalid",
        "localhost",
        "test",
    }
)


def email_domain_of(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()
