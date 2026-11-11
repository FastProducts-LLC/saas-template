"""AI draft generation use cases — platform-cost, no credit metering."""

import json
import re
import secrets
import uuid
from typing import Any

from app.core.policy import (
    BLOG_EXCERPT_MAX_LENGTH,
    BLOG_META_DESCRIPTION_MAX_LENGTH,
    BLOG_META_TITLE_MAX_LENGTH,
    BLOG_TITLE_MAX_LENGTH,
)
from app.domains.blog.application.ports import (
    BlogGenerationJobRepository,
    BlogPostRepository,
    DraftLlm,
)
from app.domains.blog.application.use_cases import CreateBlogPost
from app.domains.blog.domain.entities import BlogGenerationJob, GenerationJobStatus, PostStatus
from app.domains.blog.domain.errors import BlogSlugConflict
from app.domains.blog.domain.services import (
    SLOP_PHRASES,
    find_slop,
    normalize_markdown,
    normalize_tags,
    slugify,
)
from app.domains.llm.domain.entities import LlmProvider


def _clamp(value: str | None, max_len: int) -> str:
    text = (value or "").strip()
    return text[:max_len]


def _parse_draft_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def _build_prompt(job: BlogGenerationJob) -> str:
    keywords = ", ".join(job.keywords) if job.keywords else "(none)"
    notes = job.notes.strip() if job.notes else "(none)"
    slop_list = ", ".join(f'"{p}"' for p in SLOP_PHRASES)
    return (
        "Write a blog post draft as STRICT JSON with keys: "
        "title, excerpt, content, meta_title, meta_description, tags.\n"
        "Constraints:\n"
        "- excerpt ≤ 400 characters\n"
        "- meta_title ≤ 65 characters\n"
        "- meta_description ≤ 155 characters\n"
        "- content: 600-900 word markdown with ## sections\n"
        "- Use REAL newline characters — a blank line between paragraphs, "
        "each heading on its own line — never a single-line body\n"
        f"- Forbid these phrases: {slop_list}\n"
        f"- tags: array of short lowercase topic tags\n"
        f"Topic: {job.topic}\n"
        f"Keywords: {keywords}\n"
        f"Notes: {notes}\n"
        "Return ONLY the JSON object."
    )


class RequestDraftGeneration:
    def __init__(self, jobs_repo: BlogGenerationJobRepository) -> None:
        self.jobs_repo = jobs_repo

    async def execute(
        self,
        *,
        topic: str,
        keywords: list[str] | None,
        notes: str | None,
        provider: str,
        requested_by_id: uuid.UUID,
    ) -> BlogGenerationJob:
        topic_clean = topic.strip()
        if not topic_clean:
            raise ValueError("topic must be non-empty")
        job = BlogGenerationJob(
            topic=topic_clean,
            keywords=normalize_tags(keywords or []),
            notes=(notes.strip() if notes and notes.strip() else None),
            provider=provider,
            status=GenerationJobStatus.PENDING,
            requested_by_id=requested_by_id,
        )
        await self.jobs_repo.add(job)
        return job


class GenerateDraftPost:
    def __init__(
        self,
        jobs_repo: BlogGenerationJobRepository,
        posts_repo: BlogPostRepository,
        llm: DraftLlm,
    ) -> None:
        self.jobs_repo = jobs_repo
        self.posts_repo = posts_repo
        self.llm = llm

    async def execute(self, job_id: uuid.UUID) -> None:
        job = await self.jobs_repo.get(job_id)
        if job is None:
            return
        if job.status is not GenerationJobStatus.PENDING:
            return  # idempotent for acks_late redelivery

        provider = LlmProvider(job.provider)
        prompt = _build_prompt(job)
        data = await self._complete_json(provider, prompt)
        if data is None:
            job.fail("model returned invalid JSON")
            return

        content = normalize_markdown(str(data.get("content") or ""))
        slop = find_slop(content)
        if slop:
            rewrite = f"{prompt}\n\nRewrite without these phrases: {', '.join(slop)}"
            data = await self._complete_json(provider, rewrite)
            if data is None:
                job.fail("model returned invalid JSON")
                return
            content = normalize_markdown(str(data.get("content") or ""))
            slop = find_slop(content)
            if slop:
                job.fail(f"draft still contains banned phrases: {', '.join(slop)}")
                return

        title = _clamp(str(data.get("title") or job.topic), BLOG_TITLE_MAX_LENGTH)
        excerpt = _clamp(str(data.get("excerpt") or title), BLOG_EXCERPT_MAX_LENGTH)
        if not excerpt:
            excerpt = title[:BLOG_EXCERPT_MAX_LENGTH]
        meta_title = data.get("meta_title")
        meta_description = data.get("meta_description")
        meta_title_s = _clamp(str(meta_title), BLOG_META_TITLE_MAX_LENGTH) if meta_title else None
        meta_desc_s = (
            _clamp(str(meta_description), BLOG_META_DESCRIPTION_MAX_LENGTH)
            if meta_description
            else None
        )
        raw_tags = data.get("tags") or []
        tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []

        create = CreateBlogPost(self.posts_repo)
        try:
            post = await create.execute(
                title=title,
                slug=None,
                excerpt=excerpt,
                content=content or title,
                cover_image=None,
                meta_title=meta_title_s or None,
                meta_description=meta_desc_s or None,
                status=PostStatus.DRAFT,
                author_id=job.requested_by_id,
                tags=tags,
            )
        except BlogSlugConflict:
            post = await create.execute(
                title=title,
                slug=f"{slugify(title)}-{secrets.token_hex(3)}",
                excerpt=excerpt,
                content=content or title,
                cover_image=None,
                meta_title=meta_title_s or None,
                meta_description=meta_desc_s or None,
                status=PostStatus.DRAFT,
                author_id=job.requested_by_id,
                tags=tags,
            )
        job.succeed(post.id)

    async def _complete_json(self, provider: LlmProvider, prompt: str) -> dict[str, Any] | None:
        last_error: str | None = None
        current = prompt
        for _ in range(2):
            if last_error is not None:
                current = f"{prompt}\n\nPrevious response was invalid JSON: {last_error}"
            result = await self.llm.complete(provider, current, max_tokens=4096)
            try:
                return _parse_draft_json(result.text)
            except (json.JSONDecodeError, ValueError, AttributeError, TypeError) as exc:
                last_error = str(exc)
        return None
