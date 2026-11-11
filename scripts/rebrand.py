#!/usr/bin/env python3
"""One-shot mechanical rebrand of the SaaS template.

Reads deployment settings and the display name from shared/brand.toml.
Rewrites the placeholder app slug (`myapp`), domain (`your-domain.com`),
and GHCR owner (`your-org`) across the platform files, renaming per-app files
(compose overlay, Caddy vhost, deploy workflow, env examples) via `git mv`,
and optionally renumbers the dev port cluster 21427-21431.

Usage:
    python3 scripts/rebrand.py
    python3 scripts/rebrand.py --slug acme --domain acme.com
    python3 scripts/rebrand.py --slug acme --domain acme.com --ghcr-org acme-inc --name "Acme" --port-base 22000
    python3 scripts/rebrand.py --slug acme --domain acme.com --dry-run

Notes:
    - docs/customization.md is intentionally never rewritten: it documents
      the placeholder convention itself.
    - Flags override TOML values and are written back, preserving formatting.
      Each deployment setting still at its placeholder is skipped independently.
    - Changed runs regenerate brand artifacts; --no-gen skips generation.
      --dry-run only prints the plan, including TOML updates.
    - Without shared/brand.toml, --slug and --domain are required; write-back
      and generation are skipped for compatibility with older checkouts.
    - Ends with a sanity sweep that prints any leftover placeholder
      occurrences (file:line) so nothing slips through silently.

Stdlib only — no dependencies, runs anywhere Python 3.11+ exists.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OLD_SLUG = "myapp"
OLD_DOMAIN = "your-domain.com"
OLD_GHCR_ORG = "your-org"
OLD_NAME = "SaaS Template"
OLD_PORTS = (21427, 21428, 21429, 21430, 21431)

# Per-app files whose *names* carry the slug — renamed with `git mv`
# (falls back to os.rename outside a git checkout).
RENAME_PATTERNS = (
    "docker-compose.{slug}.yml",
    "caddy.d/{slug}.caddy",
    ".github/workflows/deploy-{slug}.yml",
    "env/{slug}.env.example",
    ".env.{slug}-deploy.example",
)

# Files whose *content* mentions the slug (patterns resolve post-rename).
SLUG_CONTENT_PATTERNS = RENAME_PATTERNS + (
    "docker-compose.yml",
    "docker-compose.prod.yml",
    ".github/workflows/cleanup-buildcache.yml",
    "setup-platform.sh",
    "deploy.sh",
    "scripts/rollout.sh",
    "scripts/check_env_examples.py",
    ".env.prod.example",
    "docs/backups.md",
    "docs/provisioning.md",
    "docs/runbook.md",
    "docs/monitoring.md",
    "README.md",
    "mobile/app.json",  # expo slug + deep-link scheme
    # Comments pointing at the caddy.d/<slug>.caddy vhost (CSP notes).
    "frontend/src/shared/lib/analytics.ts",
    "frontend/src/shared/lib/sentry.ts",
    "frontend/nginx.conf",
)

# Files whose content mentions the placeholder domain (incl. the
# support@your-domain.com / ops@your-domain.com mailboxes — plain substring
# replacement of the domain rewrites those too).
DOMAIN_CONTENT_PATTERNS = (
    "caddy.d/{slug}.caddy",
    "env/{slug}.env.example",
    "Caddyfile",
    ".github/workflows/deploy-{slug}.yml",
    "frontend/public/docs/api.md",
    "frontend/src/features/legal/TERMS_OF_SERVICE.md",
    "frontend/src/features/legal/PRIVACY_POLICY.md",
    "frontend/src/features/api-keys/components/ApiKeysPage.tsx",
    "setup-platform.sh",
    "docs/provisioning.md",
    "docs/monitoring.md",
)

# Only application-facing names; convention docs and generated files have
# separate owners and deliberately retain the template's identity.
NAME_CONTENT_PATTERNS = (
    ".env.example",
    "env/{slug}.env.example",
    "frontend/public/docs/api.md",
    "backend/pyproject.toml",
    "README.md",
)

# Files that pin the dev port cluster (only rewritten with --port-base).
PORT_CONTENT_PATTERNS = (
    "docker-compose.yml",
    "backend/app/core/config.py",
    "frontend/vite.config.ts",
    "frontend/playwright.config.ts",
    "frontend/e2e/global-setup.ts",
    "frontend/e2e/helpers/mailpit.ts",
    "README.md",
    ".env.example",
    "docs/conventions.md",
    "mobile/README.md",
    "mobile/src/shared/config.ts",
)

# Extra locations swept for stragglers after the rewrite.
SWEEP_DIRS = ("frontend/src", "backend/app", "mobile/src", "env")
# Convention docs deliberately show the old slug; TOML can retain independently
# unchosen settings. Neither is an application/deployment straggler.
SWEEP_SKIP = ("docs/customization.md", "docs/conventions.md", "shared/brand.toml")
GENERATED_BRAND_FILES = (
    "frontend/src/shared/lib/brand.ts",
    "mobile/src/shared/lib/brand.ts",
    "backend/app/core/brand.py",
)
GHCR_CONTENT_PATTERNS = (
    "docker-compose.{slug}.yml",
    ".github/workflows/deploy-{slug}.yml",
)

# Words that already appear throughout the codebase — using one as the slug
# would corrupt unrelated text via substring collisions.
SLUG_BLOCKLIST = frozenset({
    "app", "apps", "api", "env", "backend", "frontend", "worker", "beat",
    "web", "dev", "prd", "stg", "prod", "test", "docs", "media", "cache",
    "caddy", "main", "stable", "compose", "docker", "valkey", "mailpit",
    "celery", "stripe", "admin", "auth", "org", "orgs", "user", "shared",
    "image", "deploy", "build", "health", "credits", "myapp",
})


@dataclass
class PlannedFile:
    """One file's rewrite: where it is now, where it ends up, and what changes."""

    source: str  # rel path before rename (read from here)
    final: str  # rel path after rename (written here)
    new_text: str = ""
    counts: dict[str, int] = field(default_factory=dict)  # token -> replacements

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def fail(msg: str) -> None:
    sys.exit(f"error: {msg}")


def validate_slug(slug: str) -> None:
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", slug):
        fail(f"slug {slug!r} must be lowercase alphanumeric+hyphens (no leading/trailing hyphen)")
    if len(slug) < 3:
        fail(f"slug {slug!r} is too short (< 3 chars) — high substring-collision risk")
    if slug in SLUG_BLOCKLIST:
        fail(f"slug {slug!r} already appears throughout the codebase — pick a distinctive name")


def validate_domain(domain: str) -> None:
    label = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    if len(domain) > 253 or not re.fullmatch(rf"(?:{label}\.)+[a-z]{{2,63}}", domain):
        fail(f"domain {domain!r} does not look like a bare domain (e.g. acme.com)")


def validate_port_base(base: int, root: Path, port_files: list[str]) -> dict[str, str]:
    """Return {old: new} port strings; abort on range/collision problems."""
    new_ports = list(range(base, base + len(OLD_PORTS)))
    if base < 1024 or new_ports[-1] > 65535:
        fail(f"--port-base {base}: ports {new_ports[0]}-{new_ports[-1]} out of range 1024-65535")
    if set(new_ports) & set(OLD_PORTS):
        fail(f"--port-base {base}: new range overlaps the current cluster {OLD_PORTS[0]}-{OLD_PORTS[-1]}")
    texts = [(rel, (root / rel).read_text()) for rel in port_files if (root / rel).exists()]
    # A completed rebrand already contains the new ports. Only check collisions
    # when there are still old ports to replace.
    if not any(str(port) in text for _, text in texts for port in OLD_PORTS):
        return {}
    collisions = []
    for rel, text in texts:
        for port in new_ports:
            if str(port) in text:
                collisions.append(f"  {rel}: {port}")
    if collisions:
        fail("new port(s) already appear in target files — pick another base: " + "; ".join(collisions))
    return {str(old): str(new) for old, new in zip(OLD_PORTS, new_ports)}


def apply_ports(text: str, port_map: dict[str, str]) -> tuple[str, dict[str, int]]:
    """Single-pass replacement so a shifted port is never rewritten twice."""
    counts = {old: text.count(old) for old in port_map if old in text}
    pattern = re.compile("|".join(sorted(port_map, key=len, reverse=True)))
    return pattern.sub(lambda m: port_map[m.group()], text), counts


def replace_placeholder(text: str, old: str, new: str) -> tuple[str, int]:
    """Keep chosen values intact even when they contain the old placeholder."""
    count = 0

    def replace(match: re.Match) -> str:
        nonlocal count
        if match.group() == old:
            count += 1
            return new
        return match.group()

    return re.sub(f"{re.escape(new)}|{re.escape(old)}", replace, text), count


def build_plan(
    root: Path, slug: str, domain: str, port_map: dict[str, str] | None,
    ghcr_org: str = OLD_GHCR_ORG,
    name: str | None = None,
) -> tuple[list[tuple[str, str]], list[PlannedFile], list[str]]:
    """Compute renames and per-file rewrites without touching anything."""
    rename_map = {}  # source rel -> final rel
    renames: list[tuple[str, str]] = []
    skipped: list[str] = []
    for pattern in RENAME_PATTERNS:
        src = pattern.format(slug=OLD_SLUG)
        dst = pattern.format(slug=slug)
        if src == dst:
            continue
        if not (root / src).exists():
            continue
        if (root / dst).exists():
            fail(f"rename target already exists: {dst}")
        rename_map[src] = dst
        renames.append((src, dst))

    # final rel path -> list of replacement jobs
    jobs: dict[str, list[str]] = {}

    def source_of(final_rel: str) -> str:
        for src, dst in rename_map.items():
            if dst == final_rel:
                return src
        return final_rel

    for pattern in SLUG_CONTENT_PATTERNS:
        if slug != OLD_SLUG:
            jobs.setdefault(pattern.format(slug=slug), []).append("slug")
    for pattern in DOMAIN_CONTENT_PATTERNS:
        if domain != OLD_DOMAIN:
            jobs.setdefault(pattern.format(slug=slug), []).append("domain")
    for pattern in GHCR_CONTENT_PATTERNS:
        if ghcr_org != OLD_GHCR_ORG:
            jobs.setdefault(pattern.format(slug=slug), []).append("ghcr_org")
    if name is not None and name != OLD_NAME:
        for pattern in NAME_CONTENT_PATTERNS:
            jobs.setdefault(pattern.format(slug=slug), []).append("name")
    if port_map:
        for rel in PORT_CONTENT_PATTERNS:
            jobs.setdefault(rel, []).append("ports")

    plan: list[PlannedFile] = []
    for final_rel in sorted(jobs):
        source_rel = source_of(final_rel)
        path = root / source_rel
        if not path.exists():
            skipped.append(source_rel)
            continue
        text = path.read_text()
        planned = PlannedFile(source=source_rel, final=final_rel)
        if "ports" in jobs[final_rel] and port_map:
            text, port_counts = apply_ports(text, port_map)
            planned.counts.update(port_counts)
        if "slug" in jobs[final_rel] and OLD_SLUG in text:
            text, planned.counts[OLD_SLUG] = replace_placeholder(text, OLD_SLUG, slug)
        if "domain" in jobs[final_rel] and OLD_DOMAIN in text:
            text, planned.counts[OLD_DOMAIN] = replace_placeholder(text, OLD_DOMAIN, domain)
        old_owner = f"ghcr.io/{OLD_GHCR_ORG}/"
        if "ghcr_org" in jobs[final_rel] and old_owner in text:
            planned.counts[old_owner] = text.count(old_owner)
            text = text.replace(old_owner, f"ghcr.io/{ghcr_org}/")
        if "name" in jobs[final_rel] and OLD_NAME in text:
            text, planned.counts[OLD_NAME] = replace_placeholder(
                text, OLD_NAME, escaped_name(name, final_rel)
            )
        planned.new_text = text
        if planned.total:
            plan.append(planned)
    return renames, plan, skipped


def git_mv(root: Path, src: str, dst: str) -> str:
    """git mv, falling back to os.rename outside a git checkout."""
    try:
        subprocess.run(
            ["git", "mv", src, dst], cwd=root, check=True, capture_output=True, text=True
        )
        return "git mv"
    except (subprocess.CalledProcessError, FileNotFoundError):
        os.rename(root / src, root / dst)
        return "os.rename"


def verify_workflow(slug: str, workflow_text: str | None) -> list[str]:
    """The deploy workflow's paths: triggers must reference the renamed files."""
    problems = []
    if workflow_text is None:
        return [f".github/workflows/deploy-{slug}.yml not found — cannot verify paths: triggers"]
    for needle in (
        f"docker-compose.{slug}.yml",
        f"caddy.d/{slug}.caddy",
        f".github/workflows/deploy-{slug}.yml",
    ):
        if needle not in workflow_text:
            problems.append(f"deploy workflow does not reference {needle}")
    if slug != OLD_SLUG and OLD_SLUG in workflow_text:
        problems.append(f"deploy workflow still contains {OLD_SLUG!r}")
    return problems


def escaped_name(name: str, rel: str) -> str:
    """Escape inserted names for the string syntax of each destination."""
    if rel == ".env.example" or rel.startswith("env/") and rel.endswith(".env.example"):
        return re.sub(r'[\\"$`]', lambda match: "\\" + match.group(), name)
    if rel == "backend/pyproject.toml":
        return toml_literal(name)[1:-1]
    return name


def sweep(
    root: Path, targets: set[str], overrides: dict[str, str], skip: set[str],
    name: str | None = None,
) -> list[str]:
    """Scan the rewritten set + known source trees for leftover placeholders.

    `overrides` maps rel path -> planned content (used by --dry-run, where
    nothing was written); everything else is read from disk.
    """
    targets = set(targets)
    for rel in SWEEP_DIRS:
        base = root / rel
        if base.is_dir():
            targets.update(
                str(p.relative_to(root)) for p in base.rglob("*") if p.is_file()
            )
    targets.update(str(p.relative_to(root)) for p in root.glob(".env*.example"))

    stragglers = []
    for rel in sorted(targets - skip - set(SWEEP_SKIP)):
        text = overrides.get(rel)
        if text is None:
            path = root / rel
            if not path.is_file():
                continue
            try:
                text = path.read_text()
            except (UnicodeDecodeError, OSError):
                continue  # binary or unreadable — nothing textual to leak
        for lineno, line in enumerate(text.splitlines(), 1):
            name_left = False
            if name is not None and name != OLD_NAME:
                # A chosen name may itself contain the placeholder.
                _, count = replace_placeholder(line, OLD_NAME, escaped_name(name, rel))
                name_left = count > 0
            if OLD_SLUG in line or OLD_DOMAIN in line or OLD_GHCR_ORG in line or name_left:
                stragglers.append(f"  {rel}:{lineno}: {line.strip()}")
    return stragglers


def toml_literal(value: str | int) -> str:
    # JSON string escapes are valid TOML basic-string escapes (including controls).
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")


def set_toml_value(text: str, section: str, key: str, value: str | int) -> str:
    """Replace only a scalar's value, retaining comments and original newlines."""
    string = "|".join((
        r'''"""(?:\\[\s\S]|(?!""")[^\\])*"""''',
        r"'''[\s\S]*?'''",
        r'''"(?:\\.|[^"\\\r\n])*"''',
        r"'[^'\r\n]*'",
    ))
    # Consume strings and comments as tokens too, so a multiline string cannot
    # impersonate a table header or a key on a subsequent line.
    token = re.compile(
        rf"(?P<comment>\#[^\r\n]*)|"
        rf"^[ \t]*\[(?P<section>[^\]\r\n]+)\][ \t]*(?=\#|\r?$)|"
        rf"^[ \t]*(?P<key>[A-Za-z0-9_-]+|\"[^\"\r\n]*\"|'[^'\r\n]*')[ \t]*=[ \t]*"
        rf"(?P<value>{string}|[+-]?[0-9][0-9_]*)(?=[ \t]*(?:\#|\r?$))|"
        rf"(?:{string})",
        re.MULTILINE,
    )
    current = None
    for match in token.finditer(text):
        if match.group("section") is not None:
            current = match.group("section").strip().strip("\"'")
        elif current == section and (match.group("key") or "").strip("\"'") == key:
            start, end = match.span("value")
            return text[:start] + toml_literal(value) + text[end:]
    fail(f"shared/brand.toml: missing or unsupported [{section}].{key} assignment")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--slug", help="new app slug (defaults to [deploy].slug)")
    parser.add_argument("--domain", help="production domain (defaults to [deploy].domain)")
    parser.add_argument("--ghcr-org", help="lowercase GitHub image owner (defaults to [deploy].ghcr_org)")
    parser.add_argument("--name", help="brand display name (defaults to [brand].name)")
    parser.add_argument("--port-base", type=int, help=f"renumber dev ports {OLD_PORTS[0]}-{OLD_PORTS[-1]} to N..N+4")
    parser.add_argument("--dry-run", action="store_true", help="print the plan without writing anything")
    parser.add_argument("--no-gen", action="store_true", help="skip regenerating brand artifacts")
    parser.add_argument("--root", type=Path, default=ROOT, help="repo root to operate on (default: this checkout)")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        fail(f"--root {root} is not a directory")
    brand_path = root / "shared/brand.toml"
    brand_text = None
    data = {}
    if brand_path.exists():
        try:
            brand_text = brand_path.read_bytes().decode("utf-8")
            data = tomllib.loads(brand_text)
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            fail(f"shared/brand.toml: {' '.join(str(exc).splitlines())}")
    else:
        if args.slug is None or args.domain is None:
            fail("shared/brand.toml not found: --slug and --domain are required")
        print("note: shared/brand.toml not found; TOML write-back and gen_brand skipped")

    placeholders = {
        "slug": OLD_SLUG, "domain": OLD_DOMAIN,
        "ghcr_org": OLD_GHCR_ORG, "port_base": OLD_PORTS[0],
    }
    updates: list[tuple[str, str, str | int]] = []
    for key in (*placeholders, "name"):
        section = "brand" if key == "name" else "deploy"
        table = data.get(section, {})
        if not isinstance(table, dict):
            fail(f"shared/brand.toml: [{section}] must be a table")
        flag = getattr(args, key)
        value = flag if flag is not None else table.get(key, placeholders.get(key))
        if brand_text is not None and key not in table:
            fail(f"shared/brand.toml: missing [{section}].{key}")
        if key == "port_base":
            if type(value) is not int:
                fail("[deploy].port_base must be an integer")
        elif value is not None or brand_text is not None:
            if not isinstance(value, str) or not value.strip():
                fail(f"[{section}].{key} must be a non-empty string")
        # The legacy CLI accepted uppercase domains and normalized them.
        if key == "domain" and flag is not None:
            value = value.lower()
        setattr(args, key, value)
        if brand_text is not None and flag is not None and value != table[key]:
            updates.append((section, key, value))

    if args.slug != OLD_SLUG:
        validate_slug(args.slug)
    validate_domain(args.domain)
    if len(args.ghcr_org) > 39 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.ghcr_org):
        fail(f"ghcr_org {args.ghcr_org!r} must be a lowercase GitHub org name")

    port_map = None
    if args.port_base != OLD_PORTS[0]:
        port_map = validate_port_base(args.port_base, root, list(PORT_CONTENT_PATTERNS))

    for key, placeholder in placeholders.items():
        if getattr(args, key) == placeholder:
            print(f"note: [deploy].{key} is still the placeholder ({placeholder}); skipping")
    if args.name == OLD_NAME:
        print(f"note: [brand].name is still the placeholder ({OLD_NAME}); skipping")

    # This address is generated into each brand module; keep its placeholder
    # domain in step with the deployment domain, leaving custom addresses alone.
    support_email = data.get("brand", {}).get("support_email")
    if args.domain != OLD_DOMAIN and isinstance(support_email, str) and support_email.endswith("@" + OLD_DOMAIN):
        updates.append(("brand", "support_email", support_email.replace(OLD_DOMAIN, args.domain)))
    new_brand_text = brand_text
    for section, key, value in updates:
        new_brand_text = set_toml_value(new_brand_text, section, key, value)
    if new_brand_text is not None:
        try:
            tomllib.loads(new_brand_text)
        except tomllib.TOMLDecodeError as exc:
            fail(f"shared/brand.toml update: {' '.join(str(exc).splitlines())}")

    renames, plan, skipped = build_plan(root, args.slug, args.domain, port_map, args.ghcr_org, args.name)
    generator = [sys.executable, str(root / "scripts/gen_brand.py")]
    generate = brand_text is not None and not args.no_gen
    changed = bool(renames or plan or updates)
    if not changed and generate:
        # Check for stale generated artifacts even when no mechanical rewrites
        # remain, without rewriting files on an idempotent run.
        result = subprocess.run(generator + ["--check"], cwd=root, capture_output=True, text=True)
        changed = result.returncode != 0
    if not changed:
        print("nothing to rebrand — set [deploy] in shared/brand.toml (or pass flags)")
        return
    mode = "DRY RUN — nothing written" if args.dry_run else "rebrand"
    print(f"== {mode}: {OLD_SLUG} -> {args.slug}, {OLD_DOMAIN} -> {args.domain} ==\n")

    # -- Renames -------------------------------------------------------------
    for src, dst in renames:
        if args.dry_run:
            print(f"rename  {src} -> {dst}")
        else:
            how = git_mv(root, src, dst)
            print(f"rename  {src} -> {dst}  ({how})")
    for rel in skipped:
        print(f"skip    {rel} (not found)")

    # -- Content rewrites ----------------------------------------------------
    print()
    for planned in plan:
        detail = ", ".join(f"{old} x{n}" for old, n in planned.counts.items())
        print(f"rewrite {planned.final}  ({detail})")
        if not args.dry_run:
            (root / planned.final).write_text(planned.new_text)
    print("\nnote: docs/customization.md intentionally untouched (documents the placeholder convention)")

    # -- TOML write-back and generated artifacts ------------------------------
    for section, key, value in updates:
        action = "would set" if args.dry_run else "set"
        print(f"{action} [{section}].{key} = {toml_literal(value)}")
    if updates and not args.dry_run:
        brand_path.write_bytes(new_brand_text.encode("utf-8"))
    gen_ran = False
    if generate and not args.dry_run:
        sys.stdout.flush()
        result = subprocess.run(generator, cwd=root)
        if result.returncode:
            fail(f"gen_brand.py failed (exit {result.returncode})")
        gen_ran = True

    # -- Verify the deploy workflow's paths: triggers ------------------------
    workflow_rel = f".github/workflows/deploy-{args.slug}.yml"
    workflow_text = next((p.new_text for p in plan if p.final == workflow_rel), None)
    if workflow_text is None and (root / workflow_rel).exists():
        workflow_text = (root / workflow_rel).read_text()
    problems = verify_workflow(args.slug, workflow_text)
    if problems:
        for p in problems:
            print(f"WARNING: {p}")
    else:
        print(f"verified: {workflow_rel} paths: triggers reference the renamed compose/caddy files")

    # -- Sanity sweep for stragglers ------------------------------------------
    targets = {p.final for p in plan}
    if args.dry_run:
        # Nothing was written: sweep the planned contents, and skip the
        # rename sources (they vanish once the real run moves them).
        overrides = {p.final: p.new_text for p in plan}
        sweep_skip = {src for src, _ in renames}
        sweep_skip.update(GENERATED_BRAND_FILES)
        print("note: generated brand files will be regenerated by gen_brand.py; omitted from the dry-run sweep")
    else:
        overrides = {}  # everything is on disk now
        sweep_skip = set()
    stragglers = sweep(root, targets, overrides, sweep_skip, args.name)
    name_label = f" / {OLD_NAME!r}" if args.name is not None and args.name != OLD_NAME else ""
    if stragglers:
        print(
            f"\nleftover {OLD_SLUG!r} / {OLD_DOMAIN!r} / {OLD_GHCR_ORG!r}{name_label} occurrences "
            "(review manually):"
        )
        print("\n".join(stragglers))
    else:
        print(
            f"\nsweep clean: no leftover {OLD_SLUG!r}, {OLD_DOMAIN!r}, or "
            f"{OLD_GHCR_ORG!r}{name_label} in the rewritten set"
        )

    # -- Summary ---------------------------------------------------------------
    total = sum(p.total for p in plan)
    print("\n== summary ==")
    print(f"  files renamed:    {len(renames)}")
    print(f"  files rewritten:  {len(plan)}")
    print(f"  replacements:     {total}")
    print(f"  GHCR org:         {args.ghcr_org}")
    print(f"  gen_brand ran:    {'yes' if gen_ran else 'no'}")
    if port_map:
        print(f"  ports:            {OLD_PORTS[0]}-{OLD_PORTS[-1]} -> {args.port_base}-{args.port_base + 4}")
    if args.name is not None:
        print(f"  brand name:       {args.name!r}")


if __name__ == "__main__":
    main()
