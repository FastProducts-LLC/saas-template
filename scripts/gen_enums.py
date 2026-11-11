#!/usr/bin/env python3
"""Generate TypeScript unions from the backend domain enums (the single source of truth).

The backend's pure-Python domain enums (Role, CreditPack, GenerationStatus, …)
are mirrored as hand-written string unions in the web and mobile clients —
which drift silently (nothing fails at build time when a member is added).
This script parses the enum classes with `ast` (no backend imports needed) and
emits one shared enums module per client; feature `model/types.ts` files
re-export from it.

Usage:
    python3 scripts/gen_enums.py           # write all generated files
    python3 scripts/gen_enums.py --check   # exit 1 if any generated file is stale (CI)

Outputs:
    frontend/src/shared/api/enums.ts
    mobile/src/shared/api/enums.ts

Stdlib only — no dependencies, runs anywhere Python 3.11+ exists.

Adding an enum: add a (file, class) entry to ENUM_SOURCES below and rerun.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (backend file, enum class name) — order defines output order.
ENUM_SOURCES: list[tuple[str, str]] = [
    ("backend/app/domains/organizations/domain/entities.py", "Role"),
    ("backend/app/domains/credits/domain/value_objects.py", "CreditAction"),
    ("backend/app/domains/credits/domain/value_objects.py", "CreditPack"),
    ("backend/app/domains/credits/domain/value_objects.py", "ReservationStatus"),
    ("backend/app/domains/credits/domain/value_objects.py", "TransactionType"),
    ("backend/app/domains/generations/domain/entities.py", "GenerationStatus"),
    ("backend/app/domains/privacy_requests/domain/entities.py", "PrivacyRequestStatus"),
    ("backend/app/domains/blog/domain/entities.py", "PostStatus"),
    ("backend/app/domains/community/domain/entities.py", "MembershipTier"),
    ("backend/app/domains/community/domain/entities.py", "SubscriptionStatus"),
    ("backend/app/domains/community/domain/entities.py", "ConversationType"),
    ("backend/app/domains/community/domain/value_objects.py", "CommunityPlan"),
    ("backend/app/domains/billing/domain/value_objects.py", "Plan"),
    ("backend/app/domains/billing/domain/value_objects.py", "BillingInterval"),
    ("backend/app/domains/billing/domain/value_objects.py", "PlanSubscriptionStatus"),
    ("backend/app/domains/files/domain/entities.py", "StoredFileStatus"),
    ("backend/app/domains/files/domain/entities.py", "FilePurpose"),
    ("backend/app/domains/entitlements/domain/entities.py", "EntitlementKey"),
]

HEADER = (
    "GENERATED FILE — do not edit by hand. "
    "Source: backend domain enums (python3 scripts/gen_enums.py)"
)


def extract_enum_values(path: Path, class_name: str) -> list[str]:
    """Return the string values of a `class X(str, enum.Enum)` body, in order."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            values = []
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                ):
                    values.append(stmt.value.value)
            if not values:
                sys.exit(f"{path}: {class_name} has no string members")
            return values
    sys.exit(f"{path}: enum class {class_name} not found")


def snake_upper(name: str) -> str:
    """CreditPack -> CREDIT_PACK (for the *_VALUES const names)."""
    out = [name[0]]
    for ch in name[1:]:
        if ch.isupper():
            out.append("_")
        out.append(ch)
    return "".join(out).upper()


def gen_typescript(enums: list[tuple[str, list[str], str]]) -> str:
    lines = [f"// {HEADER}", ""]
    for name, values, source in enums:
        union = " | ".join(f'"{v}"' for v in values)
        array = ", ".join(f'"{v}"' for v in values)
        lines.append(f"// {source}")
        lines.append(f"export type {name} = {union};")
        lines.append(f"export const {snake_upper(name)}_VALUES = [{array}] as const;")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify generated files are current")
    args = parser.parse_args()

    enums = []
    for rel_path, class_name in ENUM_SOURCES:
        values = extract_enum_values(ROOT / rel_path, class_name)
        enums.append((class_name, values, rel_path))

    typescript = gen_typescript(enums)
    outputs = {
        ROOT / "frontend" / "src" / "shared" / "api" / "enums.ts": typescript,
        ROOT / "mobile" / "src" / "shared" / "api" / "enums.ts": typescript,
    }

    stale = []
    for path, content in outputs.items():
        if args.check:
            if not path.exists() or path.read_text() != content:
                stale.append(path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            print(f"wrote {path.relative_to(ROOT)}")

    if stale:
        names = ", ".join(str(p.relative_to(ROOT)) for p in stale)
        sys.exit(f"stale generated files: {names} — run `python3 scripts/gen_enums.py`")
    if args.check:
        print(f"enum bridge in sync ({len(enums)} enums)")


if __name__ == "__main__":
    main()
