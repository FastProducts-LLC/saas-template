// Public article reader at "/blog/:slug". Published posts only — drafts and
// archived posts 404 from the API and render the not-found state.

import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { BRAND } from "../../../shared/lib/brand";
import { Spinner } from "../../../shared/ui";
import { MarketingFooter, MarketingHeader } from "../../home";
import { usePublishedPost } from "../api/hooks";
import ArticleBody from "./ArticleBody";

export default function BlogArticlePage() {
  const { slug = "" } = useParams();
  const { data: post, isLoading, isError } = usePublishedPost(slug);

  // Client-rendered best-effort SEO: swap title + meta description per post
  // and restore the brand defaults on unmount.
  useEffect(() => {
    if (!post) return;
    document.title = `${post.meta_title || post.title} — ${BRAND}`;
    const meta = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    const original = meta?.content ?? null;
    if (meta && post.meta_description) meta.content = post.meta_description;
    return () => {
      document.title = BRAND;
      if (meta && original !== null) meta.content = original;
    };
  }, [post]);

  return (
    <div
      data-testid="blog-article-page"
      className="min-h-screen bg-[var(--paper)] text-[var(--ink)] antialiased"
    >
      <MarketingHeader />

      <main>
        <article className="mx-auto max-w-3xl px-6 pb-20 pt-36 sm:pt-40">
          {isLoading && (
            <div className="flex justify-center py-20">
              <Spinner />
            </div>
          )}

          {isError && (
            <div data-testid="blog-article-not-found" className="py-12 text-center">
              <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold">
                Post not found
              </h1>
              <p className="mt-3 text-[var(--slate)]">
                This article may have been unpublished or moved.
              </p>
              <Link
                to={ROUTES.blog.list}
                className="mt-6 inline-block text-sm font-medium text-[var(--teal-deep)] hover:text-[var(--teal)]"
              >
                ← Back to the blog
              </Link>
            </div>
          )}

          {post && <ArticleBody post={post} />}
        </article>
      </main>

      <MarketingFooter />
    </div>
  );
}
