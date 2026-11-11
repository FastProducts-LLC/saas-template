#!/usr/bin/env python3
"""CI guard: keep the env example files in sync with backend settings.

Usage:
    python3 scripts/check_env_examples.py   # exit 1 with a report when out of sync

AST-parses the Settings class in backend/app/core/config.py (no imports, so
it never needs pydantic installed) and cross-checks it against the two env
example files:

    .env.example            — local development
    env/myapp.env.example   — production app secrets (per-app overlay)

Checks:
    A. every Settings field is documented in at least one example file,
       unless listed in ALLOWED_UNDOCUMENTED (genuinely internal knobs);
    B. every var in the example files maps back to a Settings field, unless
       listed in ALLOWED_EXTRA / ALLOWED_EXTRA_PREFIXES (compose/deploy-only
       vars that never reach Settings);
    C. any SECRET_KEY placeholder value in an example file is a member of
       config.py's _INSECURE_SECRET_KEYS set, so the production boot guard
       recognizes (and rejects) a copy-pasted placeholder.

Stdlib only — no dependencies, runs anywhere Python 3.11+ exists.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "backend" / "app" / "core" / "config.py"
EXAMPLE_FILES = (
    ROOT / ".env.example",
    ROOT / "env" / "myapp.env.example",
)

# Settings fields that are deliberately absent from the example files.
# Keep this small: anything a user might reasonably tune belongs in an
# example file, not here.
ALLOWED_UNDOCUMENTED = {
    # Fixed by the compose wiring: the media volume is mounted at /app/media
    # in every environment, and backend + worker must share the same path.
    # Overriding it per-deploy would silently break generated-asset serving.
    "MEDIA_DIR",
}

# Example-file vars that are consumed by docker compose / CI, not Settings.
ALLOWED_EXTRA = {
    "APP_SHA",  # image pin written by CI into .env.<app>-deploy
}
ALLOWED_EXTRA_PREFIXES = (
    "POSTGRES_",  # dev Postgres container bootstrap (docker-compose.yml)
    "VITE_",  # frontend build/dev-server config, never read by the backend
)


def parse_settings(config_path: Path) -> tuple[list[str], set[str]]:
    """Return (annotated Settings field names, _INSECURE_SECRET_KEYS values)."""
    tree = ast.parse(config_path.read_text(), filename=str(config_path))
    fields: list[str] = []
    insecure: set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "_INSECURE_SECRET_KEYS"
                    and isinstance(node.value, ast.Set)
                ):
                    insecure = {
                        el.value
                        for el in node.value.elts
                        if isinstance(el, ast.Constant) and isinstance(el.value, str)
                    }
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            for stmt in node.body:
                # Annotated assignments only: properties, validators, and
                # model_config (a plain Assign) are skipped automatically.
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    name = stmt.target.id
                    if not name.startswith("_"):
                        fields.append(name)

    if not fields:
        sys.exit(f"no annotated fields found on Settings in {config_path} — parser out of date?")
    if not insecure:
        sys.exit(f"_INSECURE_SECRET_KEYS set literal not found in {config_path} — parser out of date?")
    return fields, insecure


def parse_env_file(path: Path) -> dict[str, str]:
    """KEY=VALUE lines; comments and blanks ignored; quotes stripped from values."""
    entries: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        entries[key] = value
    return entries


def is_allowed_extra(var: str) -> bool:
    return var in ALLOWED_EXTRA or var.startswith(ALLOWED_EXTRA_PREFIXES)


def rel(path: Path) -> str:
    """Repo-relative path for reports (absolute if outside the repo)."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args()

    fields, insecure_keys = parse_settings(CONFIG)
    examples = {path: parse_env_file(path) for path in EXAMPLE_FILES if path.exists()}
    for path in EXAMPLE_FILES:
        if path not in examples:
            sys.exit(f"missing example file: {rel(path)}")

    documented = {key for entries in examples.values() for key in entries}
    failures = 0

    # -- Check A: every Settings field is documented somewhere ---------------
    missing = [
        f for f in fields
        if f.upper() not in documented and f.upper() not in ALLOWED_UNDOCUMENTED
    ]
    if missing:
        failures += 1
        print(f"FAIL check A: {len(missing)} Settings field(s) documented in no example file:")
        for f in missing:
            print(f"  - {f.upper()}  (config.py: {f})")
    else:
        print(f"ok   check A: all {len(fields)} Settings fields documented (or allowlisted)")

    # -- Check B: every example var maps back to a Settings field ------------
    field_names = {f.upper() for f in fields}
    unknown: list[str] = []
    for path, entries in examples.items():
        for var in entries:
            if var not in field_names and not is_allowed_extra(var):
                unknown.append(f"  - {var}  ({rel(path)})")
    if unknown:
        failures += 1
        print(f"FAIL check B: {len(unknown)} example var(s) match no Settings field:")
        print("\n".join(unknown))
    else:
        total = sum(len(e) for e in examples.values())
        print(f"ok   check B: all {total} example vars map to Settings fields (or allowlisted)")

    # -- Check C: SECRET_KEY placeholders must trip the production guard -----
    bad_secrets: list[str] = []
    for path, entries in examples.items():
        value = entries.get("SECRET_KEY")
        if value is not None and value not in insecure_keys:
            bad_secrets.append(f"  - {rel(path)}: SECRET_KEY={value!r}")
    if bad_secrets:
        failures += 1
        print("FAIL check C: SECRET_KEY placeholder not in config.py's _INSECURE_SECRET_KEYS")
        print("      (the production boot guard would accept it as a real secret):")
        print("\n".join(bad_secrets))
    else:
        print("ok   check C: SECRET_KEY placeholders are recognized by the production boot guard")

    if failures:
        sys.exit(f"\nenv examples out of sync ({failures} check(s) failed) — see report above")
    print("\nenv examples in sync")


if __name__ == "__main__":
    main()
