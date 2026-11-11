"""Blog domain errors. Every internal_code exists in shared/errors.toml."""

from app.core.exceptions import ConflictError, NotFoundError


class BlogPostNotFound(NotFoundError):
    code = "blog_post_not_found"
    internal_code = "ERR_BLOG_001"


class BlogSlugConflict(ConflictError):
    code = "blog_slug_conflict"
    internal_code = "ERR_BLOG_002"


class BlogGenerationJobNotFound(NotFoundError):
    code = "blog_generation_job_not_found"
    internal_code = "ERR_BLOG_003"
