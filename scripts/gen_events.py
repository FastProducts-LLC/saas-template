#!/usr/bin/env python3
"""Generate the product-analytics event registry from shared/events.toml.

Usage:
    python3 scripts/gen_events.py           # write all generated files
    python3 scripts/gen_events.py --check   # exit 1 if any generated file is stale (CI)

Outputs:
    frontend/src/shared/lib/events.ts
    backend/app/domains/analytics/domain/events.py

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
SOURCE = ROOT / "shared" / "events.toml"

HEADER = "GENERATED FILE — do not edit by hand. Source: shared/events.toml (python3 scripts/gen_events.py)"

NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
MAX_NAME_CHARS = 40  # GA4 event-name limit
MAX_PARAMS = 25  # GA4 per-event param limit
ALLOWED_KEYS = {"area", "params", "description", "ga"}


def load() -> tuple[dict[str, dict], dict[str, dict]]:
    data = tomllib.loads(SOURCE.read_text())
    if unknown := set(data) - {"client", "server"}:
        sys.exit(f"events.toml: unknown top-level tables {sorted(unknown)} (use client/server)")
    client, server = data.get("client", {}), data.get("server", {})
    if both := set(client) & set(server):
        sys.exit(f"events.toml: events defined as both client and server: {sorted(both)}")
    for source, table in (("client", client), ("server", server)):
        for name, spec in table.items():
            where = f"[{source}.{name}]"
            if not NAME_RE.match(name) or len(name) > MAX_NAME_CHARS:
                sys.exit(f"{where}: name must be snake_case and <= {MAX_NAME_CHARS} chars")
            if extra := set(spec) - ALLOWED_KEYS:
                sys.exit(f"{where}: unknown keys {sorted(extra)}")
            for required in ("area", "params", "description"):
                if required not in spec:
                    sys.exit(f"{where}: missing `{required}`")
            params = spec["params"]
            if not isinstance(params, list) or len(params) > MAX_PARAMS:
                sys.exit(f"{where}: params must be a list of <= {MAX_PARAMS} names")
            if bad := [p for p in params if not (isinstance(p, str) and NAME_RE.match(p))]:
                sys.exit(f"{where}: param names must be snake_case, got {bad}")
            if "ga" in spec:
                if source != "client":
                    sys.exit(f"{where}: `ga` aliases only apply to client events")
                if not NAME_RE.match(spec["ga"]) or len(spec["ga"]) > MAX_NAME_CHARS:
                    sys.exit(f"{where}: ga alias must be snake_case and <= {MAX_NAME_CHARS} chars")
    return client, server


def _ts_block(const: str, table: dict[str, dict]) -> list[str]:
    lines = [f"export const {const} = {{"]
    for name, spec in table.items():
        params = ", ".join(spec["params"]) or "none"
        lines.append(f"  // {spec['description']} (params: {params})")
        lines.append(f"  {name}: {json.dumps(name)},")
    lines.append("} as const;")
    return lines


def gen_typescript(client: dict[str, dict], server: dict[str, dict]) -> str:
    lines = [
        f"// {HEADER}",
        "//",
        "// Call sites: track(EVENTS.<name>, params). CLIENT_EVENTS are the only names",
        "// the first-party ingest accepts; SERVER_EVENTS are listed for reference and",
        "// are written by the backend only — never track() them from the browser.",
        "",
        *_ts_block("CLIENT_EVENTS", client),
        "",
        *_ts_block("SERVER_EVENTS", server),
        "",
        "/** Merged view for call sites and the registry audit. */",
        "export const EVENTS = { ...CLIENT_EVENTS, ...SERVER_EVENTS } as const;",
        "",
        "export type ClientEvent = (typeof CLIENT_EVENTS)[keyof typeof CLIENT_EVENTS];",
        "export type ServerEvent = (typeof SERVER_EVENTS)[keyof typeof SERVER_EVENTS];",
        "export type AnalyticsEvent = ClientEvent | ServerEvent;",
        "",
        "/** GA4 recommended-event names for registry events that have one. The",
        " *  first-party table always stores the registry name. */",
        "export const GA_EVENT_ALIASES: Partial<Record<ClientEvent, string>> = {",
    ]
    for name, spec in client.items():
        if "ga" in spec:
            lines.append(f"  {name}: {json.dumps(spec['ga'])},")
    lines += ["};", ""]
    return "\n".join(lines)


def _py_set(const: str, table: dict[str, dict]) -> list[str]:
    lines = [f"{const}: frozenset[str] = frozenset(", "    {"]
    for name in sorted(table):
        lines.append(f"        {json.dumps(name)},")
    lines += ["    }", ")"]
    return lines


def gen_python(client: dict[str, dict], server: dict[str, dict]) -> str:
    lines = [
        '"""GENERATED FILE — do not edit by hand.',
        "",
        "Source: shared/events.toml (python3 scripts/gen_events.py)",
        "",
        "CLIENT_EVENTS is the POST /api/events allowlist; SERVER_EVENTS are the only",
        "names capture_server_event() will write.",
        '"""',
        "",
        "# Browser-originated events (source='client').",
        *_py_set("CLIENT_EVENTS", client),
        "",
        "# Backend-originated truth events (source='server').",
        *_py_set("SERVER_EVENTS", server),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify generated files are current")
    args = parser.parse_args()

    client, server = load()
    outputs = {
        ROOT / "frontend" / "src" / "shared" / "lib" / "events.ts": gen_typescript(client, server),
        ROOT / "backend" / "app" / "domains" / "analytics" / "domain" / "events.py": gen_python(
            client, server
        ),
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
        sys.exit(f"stale generated files: {names} — run `python3 scripts/gen_events.py`")
    if args.check:
        print(f"event registry in sync ({len(client)} client + {len(server)} server events)")


if __name__ == "__main__":
    main()
