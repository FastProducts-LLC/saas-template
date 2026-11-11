"""Public + admin HTTP endpoints for the blog CMS.

Public reads are unauthenticated and published-only. Authoring is
superuser-only under /admin/blog.
"""

import uuid
from datetime import timedelta
from email.utils import format_datetime
from typing import Annotated
from xml.etree import ElementTree as ET

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from fastapi.responses import Response

from app.core.brand import BRAND_DESCRIPTION, BRAND_NAME
from app.core.config import settings
from app.core.policy import ADMIN_PAGE_SIZE, BLOG_PAGE_SIZE, BLOG_TAG_MAX_LENGTH
from app.core.security import create_action_token, decode_action_token
from app.domains.admin.interface.deps import CurrentSuperuser
from app.domains.blog.application import use_cases as uc
from app.domains.blog.application.generation import RequestDraftGeneration
from app.domains.blog.domain.entities import PostStatus
from app.domains.blog.domain.errors import BlogGenerationJobNotFound, BlogPostNotFound
from app.domains.blog.infrastructure.repositories import (
    SqlAlchemyBlogGenerationJobRepository,
    SqlAlchemyBlogPostRepository,
)
from app.domains.blog.interface.deps import (
    get_blog_generation_job_repo,
    get_blog_post_repo,
    get_create_blog_post,
    get_delete_blog_post,
    get_get_preview_post,
    get_get_published_post,
    get_request_draft_generation,
    get_update_blog_post,
)
from app.domains.blog.interface.schemas import (
    AdminBlogPostOut,
    AdminBlogPostPage,
    BlogPostCreate,
    BlogPostOut,
    BlogPostPage,
    BlogPostSummaryOut,
    BlogPostUpdate,
    BlogTagCountOut,
    DraftGenerateRequest,
    GenerationJobOut,
    PreviewLinkOut,
)
from app.domains.blog.worker import enqueue_draft_generation
from app.domains.llm.domain.entities import LlmProvider
from app.domains.llm.interface.deps import get_llm_gateway

PREVIEW_LINK_TTL_DAYS = 7

# Public reader (no auth)
public_router = APIRouter(prefix="/blog", tags=["blog"])

# Superuser authoring
admin_router = APIRouter(prefix="/admin/blog", tags=["admin-blog"])

Repo = Annotated[SqlAlchemyBlogPostRepository, Depends(get_blog_post_repo)]
JobRepo = Annotated[SqlAlchemyBlogGenerationJobRepository, Depends(get_blog_generation_job_repo)]
PageParam = Annotated[int, Query(ge=1)]
PublicPageSizeParam = Annotated[int, Query(ge=1, le=50)]
AdminPageSizeParam = Annotated[int, Query(ge=1, le=100)]


@public_router.get("/posts", response_model=BlogPostPage)
async def list_published_posts(
    repo: Repo,
    page: PageParam = 1,
    page_size: PublicPageSizeParam = BLOG_PAGE_SIZE,
    q: Annotated[str | None, Query(max_length=200)] = None,
    tag: Annotated[str | None, Query(max_length=BLOG_TAG_MAX_LENGTH)] = None,
):
    items, total = await repo.list_published(
        q=q, tag=tag, limit=page_size, offset=(page - 1) * page_size
    )
    return BlogPostPage(
        items=[BlogPostSummaryOut.from_entity(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@public_router.get("/posts/{slug}", response_model=BlogPostOut)
async def get_published_post(
    slug: str,
    use_case: Annotated[uc.GetPublishedPost, Depends(get_get_published_post)],
):
    result = await use_case.execute(slug)
    return BlogPostOut.from_entity(
        result.post, author_name=result.author_name, related=result.related
    )


@public_router.get("/preview", response_model=BlogPostOut)
async def get_preview_post(
    token: Annotated[str, Query(max_length=1000)],
    use_case: Annotated[uc.GetPreviewPost, Depends(get_get_preview_post)],
):
    # Invalid/expired/wrong-purpose tokens all look like a missing post —
    # never reveal why the preview 404'd.
    payload = decode_action_token(token, "blog_preview")
    if payload is None:
        raise BlogPostNotFound("Blog post not found.")
    try:
        post_id = uuid.UUID(str(payload.get("sub")))
    except (TypeError, ValueError):
        raise BlogPostNotFound("Blog post not found.") from None
    result = await use_case.execute(post_id)
    return BlogPostOut.from_entity(result.post, author_name=result.author_name, related=[])


@public_router.get("/tags", response_model=list[BlogTagCountOut])
async def list_tags(repo: Repo):
    rows = await repo.list_tag_counts()
    return [BlogTagCountOut(tag=tag, count=count) for tag, count in rows]


@public_router.get("/rss.xml")
async def blog_rss(repo: Repo):
    items, _ = await repo.list_published(q=None, tag=None, limit=20, offset=0)
    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = BRAND_NAME
    ET.SubElement(channel, "link").text = settings.frontend_url
    ET.SubElement(channel, "description").text = BRAND_DESCRIPTION
    for post in items:
        item = ET.SubElement(channel, "item")
        link = f"{settings.frontend_url}/blog/{post.slug}"
        ET.SubElement(item, "title").text = post.title
        ET.SubElement(item, "link").text = link
        ET.SubElement(item, "guid").text = link
        if post.published_at is not None:
            ET.SubElement(item, "pubDate").text = format_datetime(post.published_at)
        ET.SubElement(item, "description").text = post.excerpt
    xml = ET.tostring(root, encoding="unicode", xml_declaration=True)
    return Response(content=xml, media_type="application/rss+xml")


@public_router.get("/sitemap.xml")
async def blog_sitemap(repo: Repo):
    items, _ = await repo.list_published(q=None, tag=None, limit=10_000, offset=0)
    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    base = settings.frontend_url.rstrip("/")
    for path in ("/", "/pricing", "/blog"):
        url_el = ET.SubElement(urlset, "url")
        ET.SubElement(url_el, "loc").text = f"{base}{path}"
    for post in items:
        url_el = ET.SubElement(urlset, "url")
        ET.SubElement(url_el, "loc").text = f"{base}/blog/{post.slug}"
        ET.SubElement(url_el, "lastmod").text = post.updated_at.date().isoformat()
    xml = ET.tostring(urlset, encoding="unicode", xml_declaration=True)
    return Response(content=xml, media_type="application/xml")


@admin_router.get("/posts", response_model=AdminBlogPostPage)
async def list_all_posts(
    _: CurrentSuperuser,
    repo: Repo,
    status_filter: Annotated[str | None, Query(alias="status", max_length=16)] = None,
    page: PageParam = 1,
    page_size: AdminPageSizeParam = ADMIN_PAGE_SIZE,
):
    parsed: PostStatus | None = None
    if status_filter:
        try:
            parsed = PostStatus(status_filter)
        except ValueError:
            parsed = None
    items, total = await repo.list_all(
        status=parsed, limit=page_size, offset=(page - 1) * page_size
    )
    return AdminBlogPostPage(
        items=[AdminBlogPostOut.from_entity(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.get("/posts/{post_id}", response_model=AdminBlogPostOut)
async def get_post(
    post_id: uuid.UUID,
    _: CurrentSuperuser,
    repo: Repo,
):
    post = await repo.get(post_id)
    if post is None:
        raise BlogPostNotFound("Blog post not found.")
    return AdminBlogPostOut.from_entity(post)


@admin_router.post("/posts", response_model=AdminBlogPostOut, status_code=status.HTTP_201_CREATED)
async def create_post(
    body: BlogPostCreate,
    admin: CurrentSuperuser,
    use_case: Annotated[uc.CreateBlogPost, Depends(get_create_blog_post)],
):
    post = await use_case.execute(
        title=body.title,
        slug=body.slug,
        excerpt=body.excerpt,
        content=body.content,
        cover_image=body.cover_image,
        meta_title=body.meta_title,
        meta_description=body.meta_description,
        status=PostStatus(body.status),
        author_id=admin.id,
        tags=body.tags,
    )
    return AdminBlogPostOut.from_entity(post)


@admin_router.patch("/posts/{post_id}", response_model=AdminBlogPostOut)
async def update_post(
    post_id: uuid.UUID,
    body: BlogPostUpdate,
    _: CurrentSuperuser,
    use_case: Annotated[uc.UpdateBlogPost, Depends(get_update_blog_post)],
):
    post = await use_case.execute(post_id, updates=body.model_dump(exclude_unset=True))
    return AdminBlogPostOut.from_entity(post)


@admin_router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: uuid.UUID,
    _: CurrentSuperuser,
    use_case: Annotated[uc.DeleteBlogPost, Depends(get_delete_blog_post)],
):
    await use_case.execute(post_id)


@admin_router.post("/posts/{post_id}/preview-link", response_model=PreviewLinkOut)
async def create_preview_link(
    post_id: uuid.UUID,
    _: CurrentSuperuser,
    repo: Repo,
):
    post = await repo.get(post_id)
    if post is None:
        raise BlogPostNotFound("Blog post not found.")
    token = create_action_token(str(post_id), "blog_preview", timedelta(days=PREVIEW_LINK_TTL_DAYS))
    base = settings.frontend_url.rstrip("/")
    return PreviewLinkOut(
        token=token,
        url=f"{base}/blog/preview?token={token}",
        expires_in_days=PREVIEW_LINK_TTL_DAYS,
    )


@admin_router.post(
    "/generate", response_model=GenerationJobOut, status_code=status.HTTP_202_ACCEPTED
)
async def generate_draft(
    body: DraftGenerateRequest,
    admin: CurrentSuperuser,
    background: BackgroundTasks,
    use_case: Annotated[RequestDraftGeneration, Depends(get_request_draft_generation)],
):
    # Fail fast before enqueueing when the chosen provider key is missing.
    get_llm_gateway().check_configured(LlmProvider(body.provider))
    job = await use_case.execute(
        topic=body.topic,
        keywords=body.keywords,
        notes=body.notes,
        provider=body.provider,
        requested_by_id=admin.id,
    )
    # Enqueued after the request transaction commits (BackgroundTasks); the
    # worker opens its own session. Enqueue-after-commit is best-effort.
    background.add_task(enqueue_draft_generation, job.id)
    return GenerationJobOut.from_entity(job)


@admin_router.get("/generate/{job_id}", response_model=GenerationJobOut)
async def get_generation_job(
    job_id: uuid.UUID,
    _: CurrentSuperuser,
    repo: JobRepo,
):
    job = await repo.get(job_id)
    if job is None:
        raise BlogGenerationJobNotFound("Generation job not found.")
    return GenerationJobOut.from_entity(job)
