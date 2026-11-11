#!/usr/bin/env python3
"""Generate brand-identity artifacts from shared/brand.toml (the single source of truth).

Usage:
    python3 scripts/gen_brand.py           # write all generated files
    python3 scripts/gen_brand.py --check   # exit 1 if anything is stale (CI)

Outputs:
    frontend/src/shared/lib/brand.ts
    mobile/src/shared/lib/brand.ts (same content — mobile has no codegen of its own)
    frontend/src/shared/styles/tokens.css
    mobile/src/shared/ui/tokens.ts
    backend/app/core/brand.py
    frontend/index.html — only the block between
        <!-- gen:brand --> ... <!-- /gen:brand -->
    (the rest of index.html is hand-maintained)
    mobile/app.json — only expo.name and expo-splash-screen backgroundColor
        (slug/scheme belong to scripts/rebrand.py)

Stdlib only (tomllib) — no dependencies, runs anywhere Python 3.11+ exists.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "shared" / "brand.toml"
INDEX_HTML = ROOT / "frontend" / "index.html"
APP_JSON = ROOT / "mobile" / "app.json"

HEADER = "GENERATED FILE — do not edit by hand. Source: shared/brand.toml (python3 scripts/gen_brand.py)"

MARKER_RE = re.compile(r"( *)<!-- gen:brand -->.*?<!-- /gen:brand -->", re.DOTALL)

COLOR_KEYS = (
    "ink", "ink_soft", "slate", "mist", "paper", "line", "teal", "teal_deep",
    "teal_glow", "success", "danger", "info",
    "canvas", "sand", "sand_line", "carbon", "carbon_soft", "lime", "lime_deep",
)
FONT_KEYS = ("display", "body", "mono", "marketing")
EMAIL_KEYS = ("background", "surface", "text", "muted", "faint", "rule", "on_accent")
LEGAL_KEYS = {
    "company_name": "companyName",
    "effective_date": "effectiveDate",
    "jurisdiction_state": "jurisdictionState",
    "jurisdiction_country": "jurisdictionCountry",
    "arbitration_venue": "arbitrationVenue",
    "minimum_age": "minimumAge",
}


def load() -> dict:
    try:
        data = tomllib.loads(SOURCE.read_text())
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        sys.exit(f"brand.toml: {' '.join(str(exc).splitlines())}")

    def invalid(section: str, key: str, reason: str) -> None:
        sys.exit(f"brand.toml: [{section}].{key} {reason}")

    for section, keys in {
        "brand": ("name", "legal_name", "tagline", "description", "support_email"),
        "deploy": ("slug", "domain", "ghcr_org", "port_base"),
        "legal": LEGAL_KEYS,
        "theme.colors": COLOR_KEYS,
        "theme.fonts": FONT_KEYS,
        "theme.email": EMAIL_KEYS,
    }.items():
        table = data
        for part in section.split("."):
            table = table.get(part) if isinstance(table, dict) else None
        for key in keys:
            value = table.get(key) if isinstance(table, dict) else None
            if key in ("port_base", "minimum_age"):
                # bool is an int subclass, but is not a valid TOML integer here.
                if type(value) is not int:
                    invalid(section, key, "must be an integer")
            elif not isinstance(value, str) or not value.strip():
                invalid(section, key, "must be a non-empty string")
            if section in ("theme.colors", "theme.email"):
                if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                    invalid(section, key, "must be a #rrggbb hex color")
            elif section == "theme.fonts":
                if any(char in value for char in '\";{}\n\r'):
                    invalid(section, key, "must not contain quotes, semicolons, braces, or newlines")

    deploy = data["deploy"]
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", deploy["slug"]):
        invalid("deploy", "slug", "must be a lowercase slug with alphanumeric ends")
    label = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    domain = deploy["domain"]
    if (
        len(domain) > 253
        or not re.fullmatch(rf"(?:{label}\.)+[a-z]{{2,63}}", domain)
    ):
        invalid("deploy", "domain", "must be a bare lowercase domain")
    org = deploy["ghcr_org"]
    if len(org) > 39 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", org):
        invalid("deploy", "ghcr_org", "must be a lowercase GitHub org name")
    if not 1024 <= deploy["port_base"] <= 65531:
        invalid("deploy", "port_base", "must be in 1024..65531")
    if "@" not in data["brand"]["support_email"]:
        invalid("brand", "support_email", "must contain @")
    if data["legal"]["minimum_age"] <= 0:
        invalid("legal", "minimum_age", "must be a positive integer")
    return data


def gen_typescript(data: dict) -> str:
    b = data["brand"]
    domain = data["deploy"]["domain"]
    legal = "\n".join(
        f"  {name}: {json.dumps(data['legal'][key])}," for key, name in LEGAL_KEYS.items()
    )
    return f"""// {HEADER}
// Single source of truth for the product identity — see docs/customization.md.
// Lives in shared/lib so both shared UI atoms and feature slices may use it.
export const BRAND = {json.dumps(b["name"])};
export const BRAND_LEGAL = {json.dumps(b["legal_name"])};
export const BRAND_TAGLINE = {json.dumps(b["tagline"])};
export const BRAND_DESCRIPTION = {json.dumps(b["description"])};
export const BRAND_DOMAIN = {json.dumps(domain)};
export const BRAND_URL = {json.dumps("https://" + domain)};
export const SUPPORT_EMAIL = {json.dumps(b["support_email"])};
export const LEGAL = {{
{legal}
}} as const;
"""


def gen_css(data: dict) -> str:
    colors, fonts = data["theme"]["colors"], data["theme"]["fonts"]
    lines = [f"/* {HEADER} */", ":root {"]
    for key in COLOR_KEYS:
        lines.append(f"  --{key.replace('_', '-')}: {colors[key]};")
    for key in FONT_KEYS:
        fallback = (
            "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
            if key == "mono" else "system-ui, sans-serif"
        )
        # Preserve literal backslashes in CSS strings instead of consuming escapes.
        font = fonts[key].replace("\\", "\\\\")
        lines.append(f'  --font-{key}: "{font}", {fallback};')
    return "\n".join([*lines, "}", ""])


def gen_mobile_tokens(data: dict) -> str:
    colors = data["theme"]["colors"]
    keys = {
        "ink": "ink", "inkSoft": "ink_soft", "slate": "slate", "mist": "mist",
        "paper": "paper", "line": "line", "teal": "teal", "tealDeep": "teal_deep",
        "tealGlow": "teal_glow",
    }
    lines = [f"// {HEADER}", "export const colors = {"]
    for name, key in keys.items():
        lines.append(f"  {name}: {json.dumps(colors[key])},")
    lines.append('  white: "#ffffff",')
    lines.append("  // Semantic markers — thin borders / text only, never filled badges.")
    for name, key in {"match": "success", "nomatch": "danger", "review": "info"}.items():
        lines.append(f"  {name}: {json.dumps(colors[key])},")
    return "\n".join([*lines, "} as const;", ""])


def gen_python(data: dict) -> str:
    b, colors = data["brand"], data["theme"]["colors"]
    domain = data["deploy"]["domain"]
    email = "\n".join(
        f"EMAIL_{key.upper()} = {json.dumps(data['theme']['email'][key])}"
        for key in EMAIL_KEYS
    )
    return f'''"""GENERATED FILE — do not edit by hand.

Source: shared/brand.toml (python3 scripts/gen_brand.py)
"""

# Default product name; the APP_NAME env var overrides it per deployment.
BRAND_NAME = {json.dumps(b["name"], ensure_ascii=False)}
BRAND_LEGAL = {json.dumps(b["legal_name"], ensure_ascii=False)}
BRAND_TAGLINE = {json.dumps(b["tagline"], ensure_ascii=False)}
BRAND_DESCRIPTION = {json.dumps(b["description"], ensure_ascii=False)}
BRAND_DOMAIN = {json.dumps(domain)}
BRAND_URL = {json.dumps("https://" + domain)}
SUPPORT_EMAIL = {json.dumps(b["support_email"], ensure_ascii=False)}

# Shared design tokens (shared/brand.toml / DESIGN.md) for surfaces
# CSS variables can't reach — inline-styled transactional email HTML.
THEME_INK = {json.dumps(colors["ink"])}
THEME_ACCENT = {json.dumps(colors["teal_deep"])}
{email}
'''


def gen_html_block(data: dict, indent: str) -> str:
    b, colors = data["brand"], data["theme"]["colors"]
    title = escape(f'{b["name"]} — {b["tagline"]}')
    lines = [
        "<!-- gen:brand -->",
        f'<meta name="theme-color" content="{colors["ink"]}" />',
        f"<title>{title}</title>",
        f'<meta name="description" content="{escape(b["description"])}" />',
        '<meta property="og:type" content="website" />',
        f'<meta property="og:title" content="{title}" />',
        f'<meta property="og:description" content="{escape(b["description"])}" />',
        f'<meta property="og:site_name" content="{escape(b["name"])}" />',
        "<!-- /gen:brand -->",
    ]
    return "\n".join(f"{indent}{line}" for line in lines)


def patched_index_html(data: dict) -> str:
    html = INDEX_HTML.read_text()
    match = MARKER_RE.search(html)
    if not match:
        sys.exit(
            "frontend/index.html is missing the <!-- gen:brand --> ... <!-- /gen:brand --> "
            "markers — restore them so the generator knows which block it owns."
        )
    return html[: match.start()] + gen_html_block(data, match.group(1)) + html[match.end():]


def patched_app_json(data: dict) -> str:
    expo = json.loads(APP_JSON.read_text())
    expo["expo"]["name"] = data["brand"]["name"]
    plugins = expo["expo"].get("plugins", [])
    for index, plugin in enumerate(plugins):
        if plugin == "expo-splash-screen":
            plugin = [plugin, {}]
            plugins[index] = plugin
        if isinstance(plugin, list) and plugin and plugin[0] == "expo-splash-screen":
            if len(plugin) != 2 or not isinstance(plugin[1], dict):
                sys.exit("mobile/app.json: expo-splash-screen plugin options must be an object")
            plugin[1]["backgroundColor"] = data["theme"]["colors"]["teal_deep"]
            break
    else:
        sys.exit("mobile/app.json: missing expo-splash-screen plugin entry")
    return json.dumps(expo, indent=2) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify generated files are current")
    args = parser.parse_args()

    data = load()
    outputs = {
        ROOT / "frontend" / "src" / "shared" / "lib" / "brand.ts": gen_typescript(data),
        ROOT / "mobile" / "src" / "shared" / "lib" / "brand.ts": gen_typescript(data),
        ROOT / "frontend" / "src" / "shared" / "styles" / "tokens.css": gen_css(data),
        ROOT / "mobile" / "src" / "shared" / "ui" / "tokens.ts": gen_mobile_tokens(data),
        ROOT / "backend" / "app" / "core" / "brand.py": gen_python(data),
        INDEX_HTML: patched_index_html(data),
        APP_JSON: patched_app_json(data),
    }

    stale = []
    wrote = False
    for path, content in outputs.items():
        if args.check:
            if not path.exists() or path.read_text() != content:
                stale.append(path)
        else:
            if not path.exists() or path.read_text() != content:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
                wrote = True
                print(f"wrote {path.relative_to(ROOT)}")

    if stale:
        names = ", ".join(str(p.relative_to(ROOT)) for p in stale)
        sys.exit(f"stale generated files: {names} — run `python3 scripts/gen_brand.py`")
    if args.check:
        print("brand artifacts in sync")
    elif not wrote:
        print("brand artifacts already up to date")


if __name__ == "__main__":
    main()
