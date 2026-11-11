"""Blog domain policy functions."""

import re

# SEO-facing slugs get more room than org slugs (50); keep in sync with
# shared/policy.toml [field_limits].blog_slug.
SLUG_MAX_LENGTH = 80

# Keep in sync with shared/policy.toml [field_limits].blog_tag / max_tags.
TAG_MAX_LENGTH = 40
MAX_TAGS = 5

# LLM-draft quality gate — case-insensitive phrase matches.
SLOP_PHRASES = (
    "in today's fast-paced",
    "delve",
    "tapestry",
    "game-changer",
    "unlock the power",
    "in conclusion",
    "look no further",
    "elevate your",
    "revolutionize",
    "seamlessly integrate",
    "it's important to note",
    "furthermore",
    "navigating the landscape",
    "in the ever-evolving",
)


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:SLUG_MAX_LENGTH].strip("-") or "post"


def normalize_tags(tags: list[str]) -> list[str]:
    """Lowercase, slugify separators, dedupe (order-preserving), cap length/count."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in tags:
        tag = re.sub(r"[^a-z0-9]+", "-", raw.lower().strip()).strip("-")
        tag = tag[:TAG_MAX_LENGTH].strip("-")
        if not tag or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
        if len(out) >= MAX_TAGS:
            break
    return out


def normalize_markdown(text: str) -> str:
    """Unflatten LLM markdown: real newlines, blank line before headings."""
    # Literal backslash-n sequences often arrive from JSON-escaped model output.
    text = text.replace("\\n", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        if re.match(r"^#{1,6}\s", line) and out and out[-1] != "":
            out.append("")
        out.append(line)
    return "\n".join(out).strip()


def find_slop(text: str) -> list[str]:
    """Return banned AI-slop phrases present (plus flattened-markdown if sparse)."""
    hits: list[str] = []
    lower = text.lower()
    for phrase in SLOP_PHRASES:
        if phrase in lower:
            hits.append(phrase)
    normalized = normalize_markdown(text)
    if normalized.count("\n\n") < 3:
        hits.append("flattened-markdown")
    return hits
