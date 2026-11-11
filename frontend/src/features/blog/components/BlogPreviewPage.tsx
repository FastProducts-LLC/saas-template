// Draft-preview reader at "/blog/preview?token=…". Token-gated; noindex.

import { useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { Alert, Spinner } from "../../../shared/ui";
import { MarketingFooter, MarketingHeader } from "../../home";
import { usePreviewPost } from "../api/hooks";
import ArticleBody from "./ArticleBody";

export default function BlogPreviewPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const { data: post, isLoading, isError } = usePreviewPost(token);

  useEffect(() => {
    const existing = document.querySelector<HTMLMetaElement>('meta[name="robots"]');
    let created: HTMLMetaElement | null = null;
    let previous: string | null = null;
    if (existing) {
      previous = existing.content;
      existing.content = "noindex";
    } else {
      created = document.createElement("meta");
      created.name = "robots";
      created.content = "noindex";
      document.head.appendChild(created);
    }
    return () => {
      if (created) {
        created.remove();
      } else if (existing && previous !== null) {
        existing.content = previous;
      }
    };
  }, []);

  return (
    <div
      data-testid="blog-preview-page"
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

          {(isError || !token) && !isLoading && (
            <div data-testid="blog-preview-not-found" className="py-12 text-center">
              <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold">
                Preview link is invalid or expired
              </h1>
              <p className="mt-3 text-[var(--slate)]">
                Ask the author for a fresh preview link, or browse published posts.
              </p>
              <Link
                to={ROUTES.blog.list}
                className="mt-6 inline-block text-sm font-medium text-[var(--teal-deep)] hover:text-[var(--teal)]"
              >
                ← Back to the blog
              </Link>
            </div>
          )}

          {post && (
            <>
              <div className="mb-8">
                <Alert tone="warning" data-testid="blog-preview-banner">
                  Draft preview — this post is not published.
                </Alert>
              </div>
              <ArticleBody post={post} />
            </>
          )}
        </article>
      </main>

      <MarketingFooter />
    </div>
  );
}
