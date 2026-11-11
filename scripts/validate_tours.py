#!/usr/bin/env python3
"""Validate that every tour step selector has a matching data-tour attribute
in the frontend source tree.

Usage:
    python3 scripts/validate_tours.py frontend/src
"""

import pathlib
import re
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_tours.py <frontend-src-dir>", file=sys.stderr)
        return 1

    src = pathlib.Path(sys.argv[1])
    if not src.is_dir():
        print(f"Not a directory: {src}", file=sys.stderr)
        return 1

    # Collect all data-tour="..." values present in the codebase
    data_tour_re = re.compile(r'data-tour=["\']([^"\']+)["\']')
    existing_hooks: set[str] = set()
    for f in src.rglob("*.tsx"):
        existing_hooks.update(data_tour_re.findall(f.read_text()))
    for f in src.rglob("*.ts"):
        existing_hooks.update(data_tour_re.findall(f.read_text()))

    # Collect all selectors referenced in tour step definitions.
    # Matches: selector: "[data-tour='foo']"
    selector_re = re.compile(r'selector:\s*["\']' + re.escape("[data-tour=") + r'[\'\\"]?([a-zA-Z0-9_-]+)[\'\\"]?' + re.escape("]") + r'["\']')
    referenced: dict[str, list[str]] = {}
    for f in src.rglob("*.tsx"):
        text = f.read_text()
        for m in selector_re.finditer(text):
            hook = m.group(1)
            referenced.setdefault(hook, []).append(str(f))

    errors = 0
    for hook, files in sorted(referenced.items()):
        if hook not in existing_hooks:
            for filepath in files:
                print(f'MISSING  data-tour="{hook}"  (referenced in {filepath})')
            errors += 1

    if errors:
        print(f"\n{errors} tour selector(s) have no matching data-tour attribute.")
        return 1

    print(f"OK — {len(referenced)} selector(s) verified, {len(existing_hooks)} hook(s) found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
