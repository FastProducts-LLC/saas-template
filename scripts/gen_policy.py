#!/usr/bin/env python3
"""Generate cross-stack policy constants from shared/policy.toml (the single source of truth).

Usage:
    python3 scripts/gen_policy.py           # write all generated files
    python3 scripts/gen_policy.py --check   # exit 1 if any generated file is stale (CI)

Outputs:
    backend/app/core/policy.py
    frontend/src/shared/lib/policy.ts

Stdlib only (tomllib) — no dependencies, runs anywhere Python 3.11+ exists.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "shared" / "policy.toml"

HEADER = "GENERATED FILE — do not edit by hand. Source: shared/policy.toml (python3 scripts/gen_policy.py)"

# (toml section, toml key, generated constant name, comment, target)
CONSTANTS: list[tuple[str, str, str, str, str]] = [
    ("password", "min_length", "PASSWORD_MIN_LENGTH",
     "Minimum password length (backend enforcement + registration form feedback).", "both"),
    ("api_keys", "prefix", "API_KEY_PREFIX",
     "Prefix on every issued API key; referenced in docs and marketing copy.", "both"),
    ("errors", "context_retention_days", "ERROR_CONTEXT_RETENTION_DAYS",
     "Days an error reference's full request context is kept in Redis.", "both"),
    ("pagination", "admin_page_size", "ADMIN_PAGE_SIZE",
     "Default page size for admin list endpoints.", "both"),
    ("pagination", "credit_history_page_size", "CREDIT_HISTORY_PAGE_SIZE",
     "Page size for the credit-ledger history views.", "both"),
    ("field_limits", "org_name", "ORG_NAME_MAX_LENGTH",
     "Max length: organization name.", "both"),
    ("field_limits", "org_intended_use", "ORG_INTENDED_USE_MAX_LENGTH",
     "Max length: organization intended-use blurb.", "both"),
    ("field_limits", "api_key_name", "API_KEY_NAME_MAX_LENGTH",
     "Max length: API key display name.", "both"),
    ("field_limits", "admin_credit_note", "ADMIN_CREDIT_NOTE_MAX_LENGTH",
     "Max length: admin credit-adjustment note.", "both"),
    ("field_limits", "privacy_request_notes", "PRIVACY_REQUEST_NOTES_MAX_LENGTH",
     "Max length: DSAR intake free-text notes.", "both"),
    ("pagination", "blog_page_size", "BLOG_PAGE_SIZE",
     "Default page size for the public blog list.", "both"),
    ("field_limits", "blog_title", "BLOG_TITLE_MAX_LENGTH",
     "Max length: blog post title.", "both"),
    ("field_limits", "blog_slug", "BLOG_SLUG_MAX_LENGTH",
     "Max length: blog post slug (also enforced by blog/domain/services.slugify).", "both"),
    ("field_limits", "blog_excerpt", "BLOG_EXCERPT_MAX_LENGTH",
     "Max length: blog post excerpt shown on list cards.", "both"),
    ("field_limits", "blog_meta_title", "BLOG_META_TITLE_MAX_LENGTH",
     "Max length: blog post SEO meta title.", "both"),
    ("field_limits", "blog_meta_description", "BLOG_META_DESCRIPTION_MAX_LENGTH",
     "Max length: blog post SEO meta description.", "both"),
    ("field_limits", "blog_cover_image_url", "BLOG_COVER_IMAGE_URL_MAX_LENGTH",
     "Max length: blog post cover-image URL.", "both"),
    ("pagination", "community_directory_page_size", "COMMUNITY_DIRECTORY_PAGE_SIZE",
     "Page size for the community member directory grid.", "both"),
    ("pagination", "community_messages_page_size", "COMMUNITY_MESSAGES_PAGE_SIZE",
     "Page size for a community conversation's message history.", "both"),
    ("field_limits", "community_handle", "COMMUNITY_HANDLE_MAX_LENGTH",
     "Max length: community handle (also enforced by community/domain/services.normalize_handle).", "both"),
    ("field_limits", "community_display_name", "COMMUNITY_DISPLAY_NAME_MAX_LENGTH",
     "Max length: community profile display name.", "both"),
    ("field_limits", "community_bio", "COMMUNITY_BIO_MAX_LENGTH",
     "Max length: community profile bio.", "both"),
    ("field_limits", "community_avatar_url", "COMMUNITY_AVATAR_URL_MAX_LENGTH",
     "Max length: community profile avatar URL.", "both"),
    ("field_limits", "community_message", "COMMUNITY_MESSAGE_MAX_LENGTH",
     "Max length: a community direct message body.", "both"),
    ("community", "premium_grace_days", "COMMUNITY_PREMIUM_GRACE_DAYS",
     "Days past current_period_end a past_due subscription keeps premium access.", "both"),
    ("field_limits", "blog_tag", "BLOG_TAG_MAX_LENGTH",
     "Max length: a single blog post tag.", "both"),
    ("blog", "max_tags", "BLOG_MAX_TAGS",
     "Max number of tags per blog post.", "both"),
    ("rate_limits", "auth_register", "RATE_LIMIT_AUTH_REGISTER",
     "Request limit per client IP: auth register.", "python"),
    ("rate_limits", "auth_login", "RATE_LIMIT_AUTH_LOGIN",
     "Request limit per client IP: auth login.", "python"),
    ("rate_limits", "auth_refresh", "RATE_LIMIT_AUTH_REFRESH",
     "Request limit per client IP: auth refresh.", "python"),
    ("rate_limits", "auth_forgot_password", "RATE_LIMIT_AUTH_FORGOT_PASSWORD",
     "Request limit per client IP: auth forgot password.", "python"),
    ("rate_limits", "auth_reset_password", "RATE_LIMIT_AUTH_RESET_PASSWORD",
     "Request limit per client IP: auth reset password.", "python"),
    ("rate_limits", "auth_verify_email", "RATE_LIMIT_AUTH_VERIFY_EMAIL",
     "Request limit per client IP: auth verify email.", "python"),
    ("rate_limits", "auth_resend_verification", "RATE_LIMIT_AUTH_RESEND_VERIFICATION",
     "Request limit per client IP: auth resend verification.", "python"),
    ("rate_limits", "auth_change_password", "RATE_LIMIT_AUTH_CHANGE_PASSWORD",
     "Request limit per client IP: auth change password.", "python"),
    ("rate_limits", "community_start_conversation", "RATE_LIMIT_COMMUNITY_START_CONVERSATION",
     "Request limit per client IP: community start conversation.", "python"),
    ("rate_limits", "community_send_message", "RATE_LIMIT_COMMUNITY_SEND_MESSAGE",
     "Request limit per client IP: community send message.", "python"),
    ("rate_limits", "generations_create", "RATE_LIMIT_GENERATIONS_CREATE",
     "Request limit per client IP: generations create.", "python"),
    ("rate_limits", "llm_complete", "RATE_LIMIT_LLM_COMPLETE",
     "Request limit per client IP: llm complete.", "python"),
    ("rate_limits", "privacy_request_submit", "RATE_LIMIT_PRIVACY_REQUEST_SUBMIT",
     "Request limit per client IP: privacy request submit.", "python"),
    ("rate_limits", "files_upload", "RATE_LIMIT_FILES_UPLOAD",
     "Request limit per client IP: file upload creation.", "python"),
    ("analytics", "activity_event_retention_days", "ACTIVITY_EVENT_RETENTION_DAYS",
     "Days a first-party activity event is kept before the daily purge (quoted in the privacy policy).", "both"),
    ("uploads", "avatar_max_bytes", "UPLOAD_AVATAR_MAX_BYTES",
     "Maximum avatar upload size in bytes.", "both"),
    ("uploads", "avatar_max_files", "UPLOAD_AVATAR_MAX_FILES",
     "Maximum confirmed avatar files per user.", "python"),
    ("uploads", "presign_ttl_seconds", "UPLOAD_PRESIGN_TTL_SECONDS",
     "Lifetime of presigned upload and download URLs in seconds.", "python"),
    ("uploads", "pending_ttl_hours", "UPLOAD_PENDING_TTL_HOURS",
     "Age in hours after which unconfirmed uploads are deleted.", "python"),
    ("billing", "plan_grace_days", "BILLING_PLAN_GRACE_DAYS",
     "Days past current_period_end a past_due organization plan keeps paid access.", "python"),
    ("billing", "trial_days", "BILLING_TRIAL_DAYS",
     "Trial duration for plan checkout; zero disables trials.", "python"),
]


def load_values() -> list[tuple[str, object, str, str]]:
    """Return [(constant_name, value, comment, target)] validated against the toml."""
    data = tomllib.loads(SOURCE.read_text())
    known = {(s, k) for s, k, _, _, _ in CONSTANTS}
    declared = {(s, k) for s, table in data.items() for k in table}
    if missing := known - declared:
        sys.exit(f"policy.toml missing keys: {sorted(missing)}")
    if unknown := declared - known:
        sys.exit(
            f"policy.toml keys not mapped to a constant: {sorted(unknown)} — "
            "add them to CONSTANTS in scripts/gen_policy.py"
        )
    out = []
    for section, key, name, comment, target in CONSTANTS:
        value = data[section][key]
        if section == "rate_limits" and (
            not isinstance(value, str)
            or re.fullmatch(r"[1-9][0-9]*/(second|minute|hour|day)", value) is None
        ):
            sys.exit(f"[{section}].{key}: expected <count>/<second|minute|hour|day> with a positive count")
        if not isinstance(value, (int, str)):
            sys.exit(f"[{section}].{key}: only int/str values are supported, got {type(value).__name__}")
        out.append((name, value, comment, target))
    return out


def gen_python(values: list[tuple[str, object, str, str]]) -> str:
    lines = [
        '"""GENERATED FILE — do not edit by hand.',
        "",
        "Source: shared/policy.toml (python3 scripts/gen_policy.py)",
        '"""',
        "",
    ]
    for name, value, comment, target in values:
        if target not in ("both", "python"):
            continue
        lines.append(f"# {comment}")
        # json.dumps matches ruff format's double-quoted string style.
        lines.append(f"{name} = {json.dumps(value)}")
        lines.append("")
    return "\n".join(lines)


def gen_typescript(values: list[tuple[str, object, str, str]]) -> str:
    lines = [f"// {HEADER}", ""]
    for name, value, comment, target in values:
        if target not in ("both", "typescript"):
            continue
        lines.append(f"// {comment}")
        lines.append(f"export const {name} = {json.dumps(value)};")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify generated files are current")
    args = parser.parse_args()

    values = load_values()
    outputs = {
        ROOT / "backend" / "app" / "core" / "policy.py": gen_python(values),
        ROOT / "frontend" / "src" / "shared" / "lib" / "policy.ts": gen_typescript(values),
    }

    stale = []
    for path, content in outputs.items():
        if args.check:
            if not path.exists() or path.read_text() != content:
                stale.append(path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_text() != content:
                path.write_text(content)
            print(f"wrote {path.relative_to(ROOT)}")

    if stale:
        names = ", ".join(str(p.relative_to(ROOT)) for p in stale)
        sys.exit(f"stale generated files: {names} — run `python3 scripts/gen_policy.py`")
    if args.check:
        print(f"policy constants in sync ({len(values)} constants)")


if __name__ == "__main__":
    main()
