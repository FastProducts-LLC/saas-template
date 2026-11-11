// Shared article body used by the public reader and the draft-preview page.

import { Link } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import Markdown, { sanitizeUrl } from "../../../shared/lib/markdown";
import { formatPostDate } from "../model/types";
import type { BlogPost } from "../model/types";

export default function ArticleBody({ post }: { post: BlogPost }) {
  return (
    <>
      <Link
        to={ROUTES.blog.list}
        data-testid="blog-article-back-link"
        className="text-sm font-medium text-[var(--teal-deep)] hover:text-[var(--teal)]"
      >
        ← Blog
      </Link>
      <p className="mt-6 font-[family-name:var(--font-mono)] text-xs text-[var(--slate)]/75 tabular-nums">
        {formatPostDate(post.published_at)}
        {post.author_name && (
          <span data-testid="blog-article-author"> · By {post.author_name}</span>
        )}
      </p>
      <h1 className="mt-3 font-[family-name:var(--font-display)] text-4xl font-bold leading-tight tracking-tight">
        {post.title}
      </h1>
      {post.tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {post.tags.map((tag) => (
            <Link
              key={tag}
              to={`${ROUTES.blog.list}?tag=${encodeURIComponent(tag)}`}
              data-testid="blog-article-tag"
              className="rounded-full border border-[var(--line)] px-2.5 py-0.5 font-[family-name:var(--font-mono)] text-[11px] text-[var(--slate)] transition-colors hover:border-[var(--teal)] hover:text-[var(--teal-deep)]"
            >
              #{tag}
            </Link>
          ))}
        </div>
      )}
      <p className="mt-4 text-lg leading-relaxed text-[var(--slate)]">{post.excerpt}</p>
      {post.cover_image && (
        <img
          src={sanitizeUrl(post.cover_image)}
          alt=""
          className="mt-8 w-full rounded-lg border border-[var(--line)] object-cover"
        />
      )}
      <div className="blog-prose mt-10">
        <Markdown content={post.content} />
      </div>

      {post.related.length > 0 && (
        <section data-testid="blog-article-related" className="mt-16">
          <h2 className="font-[family-name:var(--font-display)] text-xl font-bold tracking-tight">
            Keep reading
          </h2>
          <div className="mt-6 border-t border-[var(--line)]">
            {post.related.slice(0, 3).map((related) => (
              <article key={related.id} className="border-b border-[var(--line)] py-6">
                <h3 className="font-[family-name:var(--font-display)] text-lg font-bold tracking-tight">
                  <Link
                    to={ROUTES.blog.post(related.slug)}
                    className="transition-colors hover:text-[var(--teal-deep)]"
                  >
                    {related.title}
                  </Link>
                </h3>
                <p className="mt-1 font-[family-name:var(--font-mono)] text-xs text-[var(--slate)]/75 tabular-nums">
                  {formatPostDate(related.published_at)}
                </p>
                <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-[var(--slate)]">
                  {related.excerpt}
                </p>
              </article>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
