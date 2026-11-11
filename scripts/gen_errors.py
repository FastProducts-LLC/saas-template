#!/usr/bin/env python3
"""Generate error-code artifacts from shared/errors.toml (the single source of truth).

Usage:
    python3 scripts/gen_errors.py           # write all generated files
    python3 scripts/gen_errors.py --check   # exit 1 if any generated file is stale (CI)

Outputs:
    backend/app/core/error_codes.py
    frontend/src/shared/api/errorCatalog.ts
    mobile/src/shared/api/errorCatalog.ts
    docs/errors.md

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
SOURCE = ROOT / "shared" / "errors.toml"

SEVERITIES = {"info", "warning", "error", "critical"}
DISPLAYS = {"field", "toast", "banner", "page"}
REQUIRED = {"title", "status", "severity", "display", "user_message", "action_step", "technical_context"}
OPTIONAL = {"retry", "alert", "frontend_only", "deprecated", "params", "user_message_specific"}
PLACEHOLDER = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
PARAM_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")

HEADER = "GENERATED FILE — do not edit by hand. Source: shared/errors.toml (python3 scripts/gen_errors.py)"


def load_catalog() -> dict[str, dict]:
    catalog = tomllib.loads(SOURCE.read_text())
    for code, entry in catalog.items():
        missing = REQUIRED - entry.keys()
        unknown = entry.keys() - REQUIRED - OPTIONAL
        if missing:
            sys.exit(f"{code}: missing fields {sorted(missing)}")
        if unknown:
            sys.exit(f"{code}: unknown fields {sorted(unknown)}")
        if entry["severity"] not in SEVERITIES:
            sys.exit(f"{code}: invalid severity {entry['severity']!r}")
        if entry["display"] not in DISPLAYS:
            sys.exit(f"{code}: invalid display {entry['display']!r}")
        if "retry" in entry and set(entry["retry"]) != {"after_ms", "max"}:
            sys.exit(f"{code}: retry must be {{after_ms, max}}")
        _check_params(code, entry)
    return catalog


def _check_params(code: str, entry: dict) -> None:
    """`params` lists the values the backend may send; `user_message_specific`
    is the copy that uses them. Clients show it only when EVERY placeholder
    has a value — otherwise the plain `user_message` — so neither variant can
    ever render half-filled. `user_message` and `action_step` stay
    placeholder-free."""
    params = entry.get("params", [])
    specific = entry.get("user_message_specific")
    if not isinstance(params, list) or not all(isinstance(n, str) for n in params):
        sys.exit(f"{code}: params must be a list of names")
    for name in params:
        if not PARAM_NAME.match(name):
            sys.exit(f"{code}: param name {name!r} must be snake_case")
    for field in ("user_message", "action_step"):
        if PLACEHOLDER.search(entry[field]):
            sys.exit(f"{code}: {field} must not contain placeholders (use user_message_specific)")
    if bool(params) != bool(specific):
        sys.exit(f"{code}: params and user_message_specific must be declared together")
    if specific:
        used = set(PLACEHOLDER.findall(specific))
        if used != set(params):
            sys.exit(f"{code}: user_message_specific placeholders {sorted(used)} != params {params}")


def gen_python(catalog: dict[str, dict]) -> str:
    lines = [
        f'"""{HEADER}"""',
        "",
        "from typing import TypedDict",
        "",
        "",
        "class ErrorMeta(TypedDict):",
        "    title: str",
        "    status: int",
        "    severity: str",
        "    user_message: str",
        "    retry: tuple[int, int] | None  # (after_ms, max) — mirrors the frontend policy",
        "    params: tuple[str, ...]  # placeholder names the copy accepts",
        "",
        "",
        "ERROR_CODES: dict[str, ErrorMeta] = {",
    ]
    for code, e in catalog.items():
        if e.get("frontend_only"):
            continue  # never sent by the backend
        lines.append(f"    {code!r}: {{")
        lines.append(f"        \"title\": {e['title']!r},")
        lines.append(f"        \"status\": {e['status']},")
        lines.append(f"        \"severity\": {e['severity']!r},")
        lines.append(f"        \"user_message\": {e['user_message']!r},")
        retry = e.get("retry")
        retry_repr = f"({retry['after_ms']}, {retry['max']})" if retry else "None"
        lines.append(f"        \"retry\": {retry_repr},")
        lines.append(f"        \"params\": {tuple(e.get('params', {}))!r},")
        lines.append("    },")
    lines += ["}", ""]
    return "\n".join(lines)


def gen_typescript(catalog: dict[str, dict]) -> str:
    codes = " |\n  ".join(f'"{c}"' for c in catalog)
    entries = []
    for code, e in catalog.items():
        retry = e.get("retry")
        entry = {
            "title": e["title"],
            "status": e["status"],
            "severity": e["severity"],
            "display": e["display"],
            "message": e["user_message"],
            "action": e["action_step"],
            "retry": {"afterMs": retry["after_ms"], "max": retry["max"]} if retry else None,
        }
        if e.get("params"):
            entry["params"] = e["params"]
            entry["messageSpecific"] = e["user_message_specific"]
        if e.get("deprecated"):
            entry["deprecated"] = True
        entries.append(f'  {code}: {json.dumps(entry)},')
    body = "\n".join(entries)
    return f"""// {HEADER}

export type ErrorCode =
  {codes};

export type Severity = "info" | "warning" | "error" | "critical";
export type Display = "field" | "toast" | "banner" | "page";

export interface CatalogEntry {{
  title: string;
  status: number;
  severity: Severity;
  display: Display;
  message: string;
  action: string;
  retry: {{ afterMs: number; max: number }} | null;
  /** Param names the server may send for this code. */
  params?: string[];
  /** `message` with `{{param}}` placeholders — used only when all are present. */
  messageSpecific?: string;
  deprecated?: boolean;
}}

export type ErrorParams = Record<string, string | number>;

export const errorCatalog: Record<ErrorCode, CatalogEntry> = {{
{body}
}};

export function isErrorCode(code: string): code is ErrorCode {{
  return code in errorCatalog;
}}

/** The user-facing headline: the param-specific copy when the server sent
 * every value it needs, otherwise the generic message (never half-filled). */
export function formatErrorMessage(
  entry: Pick<CatalogEntry, "message" | "messageSpecific">,
  params: ErrorParams = {{}},
): string {{
  if (!entry.messageSpecific) return entry.message;
  let complete = true;
  const text = entry.messageSpecific.replace(/\\{{([a-z_][a-z0-9_]*)\\}}/g, (_m, name: string) => {{
    const value = params[name];
    if (typeof value === "number" && Number.isFinite(value)) return value.toLocaleString();
    if (typeof value === "string" && value.trim()) return value;
    complete = false;
    return "";
  }});
  return complete ? text : entry.message;
}}
"""


def gen_markdown(catalog: dict[str, dict]) -> str:
    out = [
        f"<!-- {HEADER} -->",
        "",
        "# Error Code Reference",
        "",
        "Support lookup table. Users report `code · ref` (the ref is the request's",
        "`error_id`); a superuser can fetch the full request context with",
        "`GET /api/admin/errors/{error_id}`.",
        "",
    ]
    for code, e in catalog.items():
        status = e["status"] or "— (frontend-only)"
        out += [
            f"## `{code}` — {e['title']}",
            "",
            f"- **HTTP status:** {status}",
            f"- **Severity:** {e['severity']} · **Display:** {e['display']}"
            + (f" · **Auto-retry:** {e['retry']['max']}× after {e['retry']['after_ms']}ms" if e.get("retry") else ""),
            f"- **User sees:** {e['user_message']} *{e['action_step']}*",
            f"- **Technical context:** {e['technical_context']}",
        ]
        if e.get("params"):
            names = ", ".join(f"`{n}`" for n in e["params"])
            out.append(f"- **Params:** {names} → *{e['user_message_specific']}*")
        if e.get("alert"):
            out.append(f"- **⚠ Ops signal:** {e['alert']}")
        out.append("")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify generated files are current")
    args = parser.parse_args()

    catalog = load_catalog()
    typescript = gen_typescript(catalog)
    outputs = {
        ROOT / "backend" / "app" / "core" / "error_codes.py": gen_python(catalog),
        ROOT / "frontend" / "src" / "shared" / "api" / "errorCatalog.ts": typescript,
        ROOT / "mobile" / "src" / "shared" / "api" / "errorCatalog.ts": typescript,
        ROOT / "docs" / "errors.md": gen_markdown(catalog),
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
        sys.exit(f"stale generated files: {names} — run `python3 scripts/gen_errors.py`")
    if args.check:
        print(f"error catalog in sync ({len(catalog)} codes)")


if __name__ == "__main__":
    main()
