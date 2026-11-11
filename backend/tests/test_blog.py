"""Unit + API tests for the blog CMS: authoring, publish lifecycle, public reads."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.domains.blog.application.use_cases import CreateBlogPost, UpdateBlogPost
from app.domains.blog.domain import BlogPost, BlogSlugConflict, PostStatus
from app.domains.blog.domain.services import normalize_tags, slugify
from app.domains.blog.infrastructure.repositories import SqlAlchemyBlogPostRepository
from tests.helpers import make_superuser, register_and_login


class FakeBlogRepo:
    def __init__(self) -> None:
        self.items: list[BlogPost] = []

    async def add(self, post: BlogPost) -> None:
        self.items.append(post)

    async def get(self, post_id: uuid.UUID) -> BlogPost | None:
        return next((p for p in self.items if p.id == post_id), None)

    async def get_by_slug(self, slug: str) -> BlogPost | None:
        return next((p for p in self.items if p.slug == slug), None)

    async def list_published(self, *, q=None, tag=None, limit=10, offset=0):
        rows = [p for p in self.items if p.status is PostStatus.PUBLISHED]
        if tag:
            rows = [p for p in rows if tag in (p.tags or [])]
        if q:
            needle = q.lower()
            rows = [
                p
                for p in rows
                if needle in p.title.lower()
                or needle in p.excerpt.lower()
                or needle in p.content.lower()
            ]
        return rows[offset : offset + limit], len(rows)

    async def list_all(self, *, status=None, limit=25, offset=0):
        rows = self.items
        if status is not None:
            rows = [p for p in rows if p.status == status]
        return rows[offset : offset + limit], len(rows)

    async def list_due_scheduled(self, *, now: datetime):
        return [
            p
            for p in self.items
            if p.status is PostStatus.SCHEDULED
            and p.published_at is not None
            and p.published_at <= now
        ]

    async def list_related(self, *, post: BlogPost, limit: int = 3):
        published = [p for p in self.items if p.status is PostStatus.PUBLISHED and p.id != post.id]
        picked: list[BlogPost] = []
        if post.tags:
            tagged = [p for p in published if set(p.tags or []) & set(post.tags)]
            tagged.sort(key=lambda p: p.published_at or p.created_at, reverse=True)
            picked = tagged[:limit]
        if len(picked) < limit:
            exclude = {post.id, *(p.id for p in picked)}
            rest = [p for p in published if p.id not in exclude]
            rest.sort(key=lambda p: p.published_at or p.created_at, reverse=True)
            picked.extend(rest[: limit - len(picked)])
        return picked

    async def get_author_name(self, author_id: uuid.UUID) -> str | None:
        return "Test User"

    async def list_tag_counts(self):
        counts: dict[str, int] = {}
        for p in self.items:
            if p.status is not PostStatus.PUBLISHED:
                continue
            for tag in p.tags or []:
                counts[tag] = counts.get(tag, 0) + 1
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

    async def delete(self, post: BlogPost) -> None:
        self.items.remove(post)

    async def increment_view_count(self, post_id: uuid.UUID) -> None:
        post = await self.get(post_id)
        if post:
            post.view_count += 1


AUTHOR_ID = uuid.uuid4()


def _create_kwargs(**overrides):
    kwargs = {
        "title": "Hello World",
        "slug": None,
        "excerpt": "An excerpt.",
        "content": "## Hi\n\nBody text.",
        "cover_image": None,
        "meta_title": None,
        "meta_description": None,
        "status": PostStatus.DRAFT,
        "author_id": AUTHOR_ID,
    }
    kwargs.update(overrides)
    return kwargs


# ---------------------------------------------------------------- unit


def test_slugify():
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("  ---  ") == "post"
    assert len(slugify("x" * 300)) <= 80


def test_normalize_tags():
    assert normalize_tags(["Python", "python", "  FastAPI  "]) == ["python", "fastapi"]
    assert len(normalize_tags(["a", "b", "c", "d", "e", "f"])) == 5


async def test_create_derives_slug_from_title():
    repo = FakeBlogRepo()
    post = await CreateBlogPost(repo).execute(**_create_kwargs(title="My First Post"))
    assert post.slug == "my-first-post"
    assert post.status is PostStatus.DRAFT
    assert post.published_at is None


async def test_create_slug_collision_raises():
    repo = FakeBlogRepo()
    await CreateBlogPost(repo).execute(**_create_kwargs())
    with pytest.raises(BlogSlugConflict):
        await CreateBlogPost(repo).execute(**_create_kwargs())


async def test_first_publish_stamps_published_at_once():
    repo = FakeBlogRepo()
    post = await CreateBlogPost(repo).execute(**_create_kwargs())
    uc = UpdateBlogPost(repo)

    published = await uc.execute(post.id, updates={"status": "published"})
    first_published_at = published.published_at
    assert first_published_at is not None

    await uc.execute(post.id, updates={"status": "draft"})
    republished = await uc.execute(post.id, updates={"status": "published"})
    assert republished.published_at == first_published_at


async def test_update_slug_conflict_excludes_self():
    repo = FakeBlogRepo()
    post = await CreateBlogPost(repo).execute(**_create_kwargs())
    other = await CreateBlogPost(repo).execute(
        **_create_kwargs(title="Other Post", slug="other-post")
    )
    # Re-sending its own slug is fine.
    updated = await UpdateBlogPost(repo).execute(post.id, updates={"slug": post.slug})
    assert updated.slug == post.slug
    # Taking another post's slug is not.
    with pytest.raises(BlogSlugConflict):
        await UpdateBlogPost(repo).execute(post.id, updates={"slug": other.slug})


def test_schedule_sets_status_and_published_at():
    post = BlogPost(
        title="Later",
        slug="later",
        excerpt="Soon.",
        content="Body.",
    )
    at = datetime.now(UTC) + timedelta(hours=2)
    post.schedule(at)
    assert post.status is PostStatus.SCHEDULED
    assert post.published_at == at


def test_scheduled_to_published_keeps_published_at():
    post = BlogPost(
        title="Later",
        slug="later",
        excerpt="Soon.",
        content="Body.",
    )
    at = datetime.now(UTC) + timedelta(hours=2)
    post.schedule(at)
    post.apply_status(PostStatus.PUBLISHED)
    assert post.status is PostStatus.PUBLISHED
    assert post.published_at == at


async def test_update_schedule_consumes_scheduled_for():
    repo = FakeBlogRepo()
    post = await CreateBlogPost(repo).execute(**_create_kwargs())
    at = datetime.now(UTC) + timedelta(days=1)
    updated = await UpdateBlogPost(repo).execute(
        post.id, updates={"status": "scheduled", "scheduled_for": at}
    )
    assert updated.status is PostStatus.SCHEDULED
    assert updated.published_at == at
    # scheduled_for is not an entity attribute.
    assert not hasattr(updated, "scheduled_for")


# ---------------------------------------------------------------- API


async def _superuser(client, db, email="admin@example.com"):
    user, headers = await register_and_login(client, email)
    await make_superuser(db, user["id"])
    return headers


POST_BODY = {
    "title": "Launch Notes",
    "excerpt": "What shipped this week.",
    "content": "## Shipped\n\n- The blog\n- Everything else",
}


async def test_admin_endpoints_require_superuser(client):
    _, headers = await register_and_login(client, "user@example.com")
    res = await client.post("/api/admin/blog/posts", json=POST_BODY, headers=headers)
    assert res.status_code == 403
    res = await client.get("/api/admin/blog/posts", headers=headers)
    assert res.status_code == 403


async def test_draft_invisible_publicly(client, db):
    headers = await _superuser(client, db)
    res = await client.post("/api/admin/blog/posts", json=POST_BODY, headers=headers)
    assert res.status_code == 201, res.text
    post = res.json()
    assert post["slug"] == "launch-notes"
    assert post["status"] == "draft"

    public_list = (await client.get("/api/blog/posts")).json()
    assert public_list["total"] == 0
    res = await client.get(f"/api/blog/posts/{post['slug']}")
    assert res.status_code == 404
    assert res.json()["code"] == "ERR_BLOG_001"


async def test_publish_lifecycle(client, db):
    headers = await _superuser(client, db)
    post = (await client.post("/api/admin/blog/posts", json=POST_BODY, headers=headers)).json()

    res = await client.patch(
        f"/api/admin/blog/posts/{post['id']}", json={"status": "published"}, headers=headers
    )
    assert res.status_code == 200, res.text
    published = res.json()
    assert published["status"] == "published"
    assert published["published_at"] is not None

    # Visible publicly now.
    public_list = (await client.get("/api/blog/posts")).json()
    assert public_list["total"] == 1
    assert public_list["items"][0]["slug"] == post["slug"]
    detail = (await client.get(f"/api/blog/posts/{post['slug']}")).json()
    assert detail["content"] == POST_BODY["content"]

    # Unpublish -> republish keeps the original published_at.
    await client.patch(
        f"/api/admin/blog/posts/{post['id']}", json={"status": "draft"}, headers=headers
    )
    res = await client.patch(
        f"/api/admin/blog/posts/{post['id']}", json={"status": "published"}, headers=headers
    )
    assert res.json()["published_at"] == published["published_at"]

    # Archive hides it publicly again.
    await client.patch(
        f"/api/admin/blog/posts/{post['id']}", json={"status": "archived"}, headers=headers
    )
    assert (await client.get(f"/api/blog/posts/{post['slug']}")).status_code == 404


async def test_slug_conflict_returns_409(client, db):
    headers = await _superuser(client, db)
    assert (
        await client.post("/api/admin/blog/posts", json=POST_BODY, headers=headers)
    ).status_code == 201
    res = await client.post("/api/admin/blog/posts", json=POST_BODY, headers=headers)
    assert res.status_code == 409
    assert res.json()["code"] == "ERR_BLOG_002"


async def test_view_count_increments_on_public_read(client, db):
    headers = await _superuser(client, db)
    post = (
        await client.post(
            "/api/admin/blog/posts", json={**POST_BODY, "status": "published"}, headers=headers
        )
    ).json()
    assert post["published_at"] is not None  # created directly as published

    await client.get(f"/api/blog/posts/{post['slug']}")
    await client.get(f"/api/blog/posts/{post['slug']}")
    admin_view = (await client.get(f"/api/admin/blog/posts/{post['id']}", headers=headers)).json()
    assert admin_view["view_count"] == 2


async def test_delete_then_404(client, db):
    headers = await _superuser(client, db)
    post = (await client.post("/api/admin/blog/posts", json=POST_BODY, headers=headers)).json()
    res = await client.delete(f"/api/admin/blog/posts/{post['id']}", headers=headers)
    assert res.status_code == 204
    res = await client.get(f"/api/admin/blog/posts/{post['id']}", headers=headers)
    assert res.status_code == 404
    assert res.json()["code"] == "ERR_BLOG_001"


async def test_admin_list_filters_by_status(client, db):
    headers = await _superuser(client, db)
    await client.post("/api/admin/blog/posts", json=POST_BODY, headers=headers)
    await client.post(
        "/api/admin/blog/posts",
        json={**POST_BODY, "title": "Second", "status": "published"},
        headers=headers,
    )

    all_posts = (await client.get("/api/admin/blog/posts", headers=headers)).json()
    assert all_posts["total"] == 2
    drafts = (await client.get("/api/admin/blog/posts?status=draft", headers=headers)).json()
    assert drafts["total"] == 1
    assert drafts["items"][0]["status"] == "draft"


async def test_tags_round_trip_and_normalize(client, db):
    headers = await _superuser(client, db)
    res = await client.post(
        "/api/admin/blog/posts",
        json={**POST_BODY, "tags": ["Python", "python", "  FastAPI  "]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    post = res.json()
    assert post["tags"] == ["python", "fastapi"]

    res = await client.patch(
        f"/api/admin/blog/posts/{post['id']}",
        json={"tags": ["Django", "django", "REST"]},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["tags"] == ["django", "rest"]


async def test_public_list_filters_by_tag(client, db):
    headers = await _superuser(client, db, email="tag-admin@example.com")
    await client.post(
        "/api/admin/blog/posts",
        json={**POST_BODY, "title": "Py Post", "tags": ["python"], "status": "published"},
        headers=headers,
    )
    await client.post(
        "/api/admin/blog/posts",
        json={
            **POST_BODY,
            "title": "Go Post",
            "tags": ["golang"],
            "status": "published",
        },
        headers=headers,
    )

    matched = (await client.get("/api/blog/posts?tag=python")).json()
    assert matched["total"] == 1
    assert matched["items"][0]["slug"] == "py-post"

    empty = (await client.get("/api/blog/posts?tag=rust")).json()
    assert empty["total"] == 0
    assert empty["items"] == []


async def test_public_list_full_text_search(client, db):
    headers = await _superuser(client, db, email="search-admin@example.com")
    await client.post(
        "/api/admin/blog/posts",
        json={
            **POST_BODY,
            "title": "Alpha",
            "content": "Contains the word xylophone in the body.",
            "status": "published",
        },
        headers=headers,
    )
    await client.post(
        "/api/admin/blog/posts",
        json={
            **POST_BODY,
            "title": "Beta",
            "content": "Nothing special here.",
            "status": "published",
        },
        headers=headers,
    )

    matched = (await client.get("/api/blog/posts?q=xylophone")).json()
    assert matched["total"] == 1
    assert matched["items"][0]["slug"] == "alpha"


async def test_public_tag_counts_published_only(client, db):
    headers = await _superuser(client, db, email="counts-admin@example.com")
    await client.post(
        "/api/admin/blog/posts",
        json={
            **POST_BODY,
            "title": "Pub One",
            "tags": ["python", "api"],
            "status": "published",
        },
        headers=headers,
    )
    await client.post(
        "/api/admin/blog/posts",
        json={
            **POST_BODY,
            "title": "Pub Two",
            "tags": ["python"],
            "status": "published",
        },
        headers=headers,
    )
    await client.post(
        "/api/admin/blog/posts",
        json={**POST_BODY, "title": "Drafty", "tags": ["secret"], "status": "draft"},
        headers=headers,
    )

    tags = (await client.get("/api/blog/tags")).json()
    by_tag = {row["tag"]: row["count"] for row in tags}
    assert by_tag["python"] == 2
    assert by_tag["api"] == 1
    assert "secret" not in by_tag


async def test_public_detail_author_and_related(client, db):
    headers = await _superuser(client, db, email="related-admin@example.com")
    # Overlapping-tag sibling (should rank first in related).
    await client.post(
        "/api/admin/blog/posts",
        json={
            **POST_BODY,
            "title": "Sibling Tagged",
            "tags": ["python"],
            "status": "published",
        },
        headers=headers,
    )
    # Recency fill (no shared tags).
    await client.post(
        "/api/admin/blog/posts",
        json={
            **POST_BODY,
            "title": "Recent Untagged",
            "tags": [],
            "status": "published",
        },
        headers=headers,
    )
    # Draft must never appear in related.
    await client.post(
        "/api/admin/blog/posts",
        json={
            **POST_BODY,
            "title": "Hidden Draft",
            "tags": ["python"],
            "status": "draft",
        },
        headers=headers,
    )
    main = (
        await client.post(
            "/api/admin/blog/posts",
            json={
                **POST_BODY,
                "title": "Main Article",
                "tags": ["python"],
                "status": "published",
            },
            headers=headers,
        )
    ).json()

    detail = (await client.get(f"/api/blog/posts/{main['slug']}")).json()
    assert detail["author_name"] == "Test User"
    related_slugs = [r["slug"] for r in detail["related"]]
    assert main["slug"] not in related_slugs
    assert "hidden-draft" not in related_slugs
    assert related_slugs[0] == "sibling-tagged"
    assert "recent-untagged" in related_slugs


async def test_rss_and_sitemap(client, db):
    headers = await _superuser(client, db, email="feed-admin@example.com")
    published = (
        await client.post(
            "/api/admin/blog/posts",
            json={**POST_BODY, "title": "Feed Item", "status": "published"},
            headers=headers,
        )
    ).json()
    draft = (
        await client.post(
            "/api/admin/blog/posts",
            json={**POST_BODY, "title": "Draft Feed", "status": "draft"},
            headers=headers,
        )
    ).json()

    rss = await client.get("/api/blog/rss.xml")
    assert rss.status_code == 200
    assert "application/rss+xml" in rss.headers["content-type"]
    assert published["slug"] in rss.text
    assert draft["slug"] not in rss.text

    sitemap = await client.get("/api/blog/sitemap.xml")
    assert sitemap.status_code == 200
    assert "application/xml" in sitemap.headers["content-type"]
    assert published["slug"] in sitemap.text
    assert draft["slug"] not in sitemap.text


async def test_schedule_post_invisible_publicly(client, db):
    headers = await _superuser(client, db, email="schedule-admin@example.com")
    post = (await client.post("/api/admin/blog/posts", json=POST_BODY, headers=headers)).json()
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()

    res = await client.patch(
        f"/api/admin/blog/posts/{post['id']}",
        json={"status": "scheduled", "scheduled_for": future},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "scheduled"
    assert body["published_at"] is not None

    assert (await client.get(f"/api/blog/posts/{post['slug']}")).status_code == 404
    public_list = (await client.get("/api/blog/posts")).json()
    assert public_list["total"] == 0


async def test_schedule_requires_scheduled_for(client, db):
    headers = await _superuser(client, db, email="schedule-req@example.com")
    post = (await client.post("/api/admin/blog/posts", json=POST_BODY, headers=headers)).json()

    res = await client.patch(
        f"/api/admin/blog/posts/{post['id']}",
        json={"status": "scheduled"},
        headers=headers,
    )
    assert res.status_code == 422


async def test_schedule_rejects_naive_datetime(client, db):
    headers = await _superuser(client, db, email="schedule-naive@example.com")
    post = (await client.post("/api/admin/blog/posts", json=POST_BODY, headers=headers)).json()

    # ISO without offset → naive after parse → 422.
    res = await client.patch(
        f"/api/admin/blog/posts/{post['id']}",
        json={"status": "scheduled", "scheduled_for": "2099-01-01T12:00:00"},
        headers=headers,
    )
    assert res.status_code == 422


# `worker.publish_due_posts()` opens its own SessionLocal against the app DB,
# not the test DB (same as credits sweep). Exercise the worker logic via
# repo.list_due_scheduled + apply_status on the test session instead.
async def test_list_due_scheduled_and_publish_flip(client, db):
    headers = await _superuser(client, db, email="due-admin@example.com")
    post = (await client.post("/api/admin/blog/posts", json=POST_BODY, headers=headers)).json()
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    res = await client.patch(
        f"/api/admin/blog/posts/{post['id']}",
        json={"status": "scheduled", "scheduled_for": future},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    post_id = uuid.UUID(post["id"])

    # Force the go-live time into the past (validator rejects past via PATCH).
    async with db.begin():
        entity = await db.get(BlogPost, post_id)
        assert entity is not None
        entity.published_at = datetime.now(UTC) - timedelta(minutes=5)

    repo = SqlAlchemyBlogPostRepository(db)
    async with db.begin():
        due = await repo.list_due_scheduled(now=datetime.now(UTC))
    assert any(p.id == post_id for p in due)

    # Mirror publish_due_posts()'s flip loop on the test session.
    async with db.begin():
        due = await repo.list_due_scheduled(now=datetime.now(UTC))
        for p in due:
            p.apply_status(PostStatus.PUBLISHED)
            p.touch()

    async with db.begin():
        entity = await db.get(BlogPost, post_id)
        assert entity is not None
        assert entity.status is PostStatus.PUBLISHED

    due = await repo.list_due_scheduled(now=datetime.now(UTC))
    assert not any(p.id == post_id for p in due)


# ---------------------------------------------------------------- preview links


async def test_preview_link_for_draft_and_no_view_bump(client, db):
    headers = await _superuser(client, db, email="preview-admin@example.com")
    post = (await client.post("/api/admin/blog/posts", json=POST_BODY, headers=headers)).json()
    assert post["status"] == "draft"
    assert post["view_count"] == 0

    link = await client.post(f"/api/admin/blog/posts/{post['id']}/preview-link", headers=headers)
    assert link.status_code == 200, link.text
    body = link.json()
    assert body["expires_in_days"] == 7
    assert body["token"]
    assert f"/blog/preview?token={body['token']}" in body["url"]

    preview = await client.get(f"/api/blog/preview?token={body['token']}")
    assert preview.status_code == 200, preview.text
    assert preview.json()["title"] == POST_BODY["title"]
    assert preview.json()["related"] == []

    # Second fetch must not bump view_count.
    assert (await client.get(f"/api/blog/preview?token={body['token']}")).status_code == 200
    admin_view = (await client.get(f"/api/admin/blog/posts/{post['id']}", headers=headers)).json()
    assert admin_view["view_count"] == 0


async def test_preview_garbage_and_wrong_purpose_token_404(client, db):
    headers = await _superuser(client, db, email="preview-bad@example.com")
    post = (await client.post("/api/admin/blog/posts", json=POST_BODY, headers=headers)).json()

    garbage = await client.get("/api/blog/preview?token=not-a-valid-jwt")
    assert garbage.status_code == 404
    assert garbage.json()["code"] == "ERR_BLOG_001"

    from app.core.security import create_action_token

    wrong = create_action_token(str(post["id"]), "verify_email", timedelta(days=7))
    res = await client.get(f"/api/blog/preview?token={wrong}")
    assert res.status_code == 404
    assert res.json()["code"] == "ERR_BLOG_001"


async def test_preview_link_unknown_post_404(client, db):
    headers = await _superuser(client, db, email="preview-missing@example.com")
    res = await client.post(f"/api/admin/blog/posts/{uuid.uuid4()}/preview-link", headers=headers)
    assert res.status_code == 404
    assert res.json()["code"] == "ERR_BLOG_001"


async def test_preview_link_requires_superuser(client):
    _, headers = await register_and_login(client, "preview-user@example.com")
    res = await client.post(f"/api/admin/blog/posts/{uuid.uuid4()}/preview-link", headers=headers)
    assert res.status_code == 403


# ---------------------------------------------------------------- AI draft generation


def test_normalize_markdown_literal_newlines_and_headings():
    from app.domains.blog.domain.services import normalize_markdown

    raw = "# Title\\n## Section\\nParagraph one.\\n\\n\\n\\nParagraph two."
    out = normalize_markdown(raw)
    assert "\n\n## Section\n" in out or out.startswith("# Title\n\n## Section")
    assert "\\n" not in out
    assert "\n\n\n" not in out

    crlf = normalize_markdown("# A\r\nBody")
    assert "\r" not in crlf
    assert crlf.startswith("# A")


def test_find_slop_hits_clean_and_flattened():
    from app.domains.blog.domain.services import find_slop

    clean = (
        "## Intro\n\n"
        "A solid opening paragraph about shipping software.\n\n"
        "## Body\n\n"
        "More concrete guidance with specifics.\n\n"
        "## Close\n\n"
        "A short wrap without filler."
    )
    assert find_slop(clean) == []

    hits = find_slop(
        "## Intro\n\nIn today's fast-paced world we delve into a tapestry.\n\n"
        "## More\n\nFurthermore we unlock the power.\n\n## End\n\nDone."
    )
    assert "in today's fast-paced" in hits
    assert "delve" in hits
    assert "tapestry" in hits
    assert "furthermore" in hits
    assert "unlock the power" in hits

    flat = find_slop("Just one block without enough separators.")
    assert "flattened-markdown" in flat


class FakeJobRepo:
    def __init__(self) -> None:
        self.items: list = []

    async def add(self, job) -> None:
        self.items.append(job)

    async def get(self, job_id: uuid.UUID):
        return next((j for j in self.items if j.id == job_id), None)

    async def list_recent(self, *, limit: int = 20):
        return self.items[:limit]


class FakeDraftLlm:
    """Returns canned `.text` responses; call_count tracks complete() calls."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.call_count = 0

    def check_configured(self, provider) -> None:
        return None

    async def complete(self, provider, prompt: str, max_tokens: int):
        from types import SimpleNamespace

        idx = min(self.call_count, len(self.responses) - 1)
        text = self.responses[idx]
        self.call_count += 1
        return SimpleNamespace(text=text)


_CLEAN_DRAFT = {
    "title": "Shipping Reliable APIs",
    "excerpt": "Practical notes on API design.",
    "content": (
        "## Why reliability matters\n\n"
        "Teams ship faster when contracts stay stable.\n\n"
        "## Concrete practices\n\n"
        "Version carefully and document failure modes.\n\n"
        "## Closing thoughts\n\n"
        "Measure what hurts and fix that first."
    ),
    "meta_title": "Shipping Reliable APIs",
    "meta_description": "Practical notes on API design and reliability.",
    "tags": ["api", "reliability"],
}

_SLOP_DRAFT = {
    **_CLEAN_DRAFT,
    "content": (
        "## Intro\n\n"
        "In today's fast-paced world we delve into APIs.\n\n"
        "## Body\n\n"
        "Furthermore this is a game-changer.\n\n"
        "## End\n\n"
        "Look no further for tips."
    ),
}


async def test_generate_draft_success_creates_post():
    import json

    from app.domains.blog.application.generation import GenerateDraftPost
    from app.domains.blog.domain.entities import BlogGenerationJob, GenerationJobStatus

    posts = FakeBlogRepo()
    jobs = FakeJobRepo()
    job = BlogGenerationJob(
        topic="Reliable APIs",
        keywords=["api"],
        provider="anthropic",
        requested_by_id=AUTHOR_ID,
    )
    await jobs.add(job)
    llm = FakeDraftLlm([json.dumps(_CLEAN_DRAFT)])

    await GenerateDraftPost(jobs, posts, llm).execute(job.id)

    assert job.status is GenerationJobStatus.SUCCEEDED
    assert job.post_id is not None
    post = await posts.get(job.post_id)
    assert post is not None
    assert post.status is PostStatus.DRAFT
    assert post.author_id == AUTHOR_ID
    assert "## Why reliability matters" in post.content
    assert "\n\n" in post.content


async def test_generate_draft_invalid_json_twice_fails():
    from app.domains.blog.application.generation import GenerateDraftPost
    from app.domains.blog.domain.entities import BlogGenerationJob, GenerationJobStatus

    posts = FakeBlogRepo()
    jobs = FakeJobRepo()
    job = BlogGenerationJob(
        topic="Broken",
        provider="anthropic",
        requested_by_id=AUTHOR_ID,
    )
    await jobs.add(job)
    llm = FakeDraftLlm(["not-json", "still-not-json"])

    await GenerateDraftPost(jobs, posts, llm).execute(job.id)

    assert job.status is GenerationJobStatus.FAILED
    assert job.error == "model returned invalid JSON"
    assert llm.call_count == 2
    assert posts.items == []


async def test_generate_draft_slop_then_clean_on_retry():
    import json

    from app.domains.blog.application.generation import GenerateDraftPost
    from app.domains.blog.domain.entities import BlogGenerationJob, GenerationJobStatus

    posts = FakeBlogRepo()
    jobs = FakeJobRepo()
    job = BlogGenerationJob(
        topic="Reliable APIs",
        provider="anthropic",
        requested_by_id=AUTHOR_ID,
    )
    await jobs.add(job)
    llm = FakeDraftLlm([json.dumps(_SLOP_DRAFT), json.dumps(_CLEAN_DRAFT)])

    await GenerateDraftPost(jobs, posts, llm).execute(job.id)

    assert job.status is GenerationJobStatus.SUCCEEDED
    assert llm.call_count == 2
    post = await posts.get(job.post_id)
    assert post is not None
    assert "delve" not in post.content.lower()


async def test_generate_draft_slug_collision_fallback():
    import json

    from app.domains.blog.application.generation import GenerateDraftPost
    from app.domains.blog.domain.entities import BlogGenerationJob, GenerationJobStatus

    posts = FakeBlogRepo()
    jobs = FakeJobRepo()
    # Pre-create a post whose slug matches the model title's slugify.
    await CreateBlogPost(posts).execute(**_create_kwargs(title="Shipping Reliable APIs"))
    job = BlogGenerationJob(
        topic="Reliable APIs",
        provider="anthropic",
        requested_by_id=AUTHOR_ID,
    )
    await jobs.add(job)
    llm = FakeDraftLlm([json.dumps(_CLEAN_DRAFT)])

    await GenerateDraftPost(jobs, posts, llm).execute(job.id)

    assert job.status is GenerationJobStatus.SUCCEEDED
    post = await posts.get(job.post_id)
    assert post is not None
    assert post.slug.startswith("shipping-reliable-apis-")
    assert len(posts.items) == 2


async def test_admin_generate_requires_superuser(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", "test-key", raising=False)
    monkeypatch.setattr(
        "app.domains.blog.interface.router.enqueue_draft_generation",
        lambda *_a, **_k: None,
    )
    _, headers = await register_and_login(client, "gen-user@example.com")
    res = await client.post(
        "/api/admin/blog/generate",
        json={"topic": "Hello"},
        headers=headers,
    )
    assert res.status_code == 403


async def test_admin_generate_and_get_job(client, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", "test-key", raising=False)
    monkeypatch.setattr(
        "app.domains.blog.interface.router.enqueue_draft_generation",
        lambda *_a, **_k: None,
    )
    # Also stub the Celery delay path in case enqueue is invoked directly.
    monkeypatch.setattr("app.domains.blog.tasks.generate_blog_draft.delay", lambda *_a, **_k: None)
    headers = await _superuser(client, db, email="gen-admin@example.com")

    res = await client.post(
        "/api/admin/blog/generate",
        json={
            "topic": "AI drafts",
            "keywords": ["writing"],
            "notes": "Keep it short",
            "provider": "anthropic",
        },
        headers=headers,
    )
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["status"] == "pending"
    assert body["topic"] == "AI drafts"
    assert body["post_id"] is None

    got = await client.get(f"/api/admin/blog/generate/{body['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["id"] == body["id"]
    assert got.json()["status"] == "pending"

    missing = await client.get(f"/api/admin/blog/generate/{uuid.uuid4()}", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["code"] == "ERR_BLOG_003"
