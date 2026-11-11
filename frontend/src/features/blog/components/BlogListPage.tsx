// Public blog index at "/blog". Renders outside AppLayout with the shared
// marketing chrome (pill nav + footer) from the home feature, like PricingPage.

import { useEffect, useState, type CSSProperties } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { BRAND } from "../../../shared/lib/brand";
import { sanitizeUrl } from "../../../shared/lib/markdown";
import { MarketingFooter, MarketingHeader } from "../../home";
import { useBlogTags, usePublishedPosts } from "../api/hooks";
import { formatPostDate } from "../model/types";

export default function BlogListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [q, setQ] = useState("");
  const activeTag = searchParams.get("tag") ?? "";

  const { data, isLoading } = usePublishedPosts(page, q, activeTag);
  const { data: tags } = useBlogTags();

  useEffect(() => {
    document.title = `Blog — ${BRAND}`;
    return () => {
      document.title = BRAND;
    };
  }, []);

  // Debounce the search box into the query used for fetching.
  useEffect(() => {
    const handle = window.setTimeout(() => {
      const next = searchInput.trim();
      setQ((prev) => {
        if (prev !== next) setPage(1);
        return next;
      });
    }, 300);
    return () => window.clearTimeout(handle);
  }, [searchInput]);

  const setActiveTag = (tag: string) => {
    setPage(1);
    const next = new URLSearchParams(searchParams);
    if (tag) next.set("tag", tag);
    else next.delete("tag");
    setSearchParams(next, { replace: true });
  };

  const lastPage = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const filtered = Boolean(q || activeTag);
  const empty = !isLoading && data && data.items.length === 0;

  return (
    <div
      data-testid="blog-list-page"
      className="min-h-screen bg-[var(--paper)] text-[var(--ink)] antialiased"
    >
      <MarketingHeader />

      <main>
        <section className="mx-auto max-w-3xl px-6 pb-20 pt-36 sm:pt-40">
          <p className="gd-hero-in text-sm font-medium text-[var(--slate)]/80">Blog</p>
          <h1
            className="gd-hero-in mt-3 font-[family-name:var(--font-display)] text-4xl font-bold tracking-tight text-[var(--ink)]"
            style={{ animationDelay: "0.08s" }}
          >
            Notes from the team
          </h1>

          <div className="mt-8">
            <input
              type="search"
              data-testid="blog-search-input"
              placeholder="Search articles…"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full rounded-full border border-[var(--line)] bg-white px-4 py-2.5 text-sm text-[var(--ink)] transition-colors placeholder:text-[var(--slate)]/50 focus:border-[var(--teal)] focus:outline-none focus:ring-2 focus:ring-[var(--teal)]/15"
            />
          </div>

          {tags && tags.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {tags.map(({ tag, count }) => {
                const selected = activeTag === tag;
                return (
                  <button
                    key={tag}
                    type="button"
                    data-testid="blog-tag-chip"
                    onClick={() => setActiveTag(selected ? "" : tag)}
                    className={`rounded-full border px-3 py-1 font-[family-name:var(--font-mono)] text-xs transition-colors ${
                      selected
                        ? "border-[var(--teal)] bg-[var(--teal)]/10 text-[var(--teal-deep)]"
                        : "border-[var(--line)] bg-white text-[var(--slate)] hover:border-[var(--slate)]/30"
                    }`}
                  >
                    #{tag} ({count})
                  </button>
                );
              })}
            </div>
          )}

          {isLoading && (
            <div className="mt-12 space-y-8">
              {[0, 1, 2].map((i) => (
                <div key={i} className="gd-skel h-24 rounded-lg" />
              ))}
            </div>
          )}

          {empty && filtered && (
            <p data-testid="blog-no-results" className="mt-12 text-[var(--slate)]">
              No matching posts.
            </p>
          )}

          {empty && !filtered && (
            <p data-testid="blog-empty-state" className="mt-12 text-[var(--slate)]">
              No posts yet — check back soon.
            </p>
          )}

          {!isLoading && data && data.items.length > 0 && (
            <div className="mt-10 border-t border-[var(--line)]">
              {data.items.map((post, i) => (
                <article
                  key={post.id}
                  data-testid="blog-post-card"
                  className="gd-stagger-item border-b border-[var(--line)] py-8"
                  style={{ "--i": i } as CSSProperties}
                >
                  <p className="font-[family-name:var(--font-mono)] text-xs text-[var(--slate)]/75 tabular-nums">
                    {formatPostDate(post.published_at)}
                  </p>
                  <h2 className="mt-2 font-[family-name:var(--font-display)] text-xl font-bold tracking-tight">
                    <Link
                      to={ROUTES.blog.post(post.slug)}
                      className="transition-colors hover:text-[var(--teal-deep)]"
                    >
                      {post.title}
                    </Link>
                  </h2>
                  {post.tags.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {post.tags.map((tag) => (
                        <span
                          key={tag}
                          data-testid="blog-post-tag"
                          className="rounded-full border border-[var(--line)] px-2 py-0.5 font-[family-name:var(--font-mono)] text-[11px] text-[var(--slate)]"
                        >
                          #{tag}
                        </span>
                      ))}
                    </div>
                  )}
                  {post.cover_image && (
                    <img
                      src={sanitizeUrl(post.cover_image)}
                      alt=""
                      loading="lazy"
                      className="mt-4 max-h-64 w-full rounded-lg border border-[var(--line)] object-cover"
                    />
                  )}
                  <p className="mt-3 text-sm leading-relaxed text-[var(--slate)]">{post.excerpt}</p>
                  <Link
                    to={ROUTES.blog.post(post.slug)}
                    className="mt-3 inline-block text-sm font-medium text-[var(--teal-deep)] hover:text-[var(--teal)]"
                  >
                    Read article →
                  </Link>
                </article>
              ))}
            </div>
          )}

          {data && data.total > data.page_size && (
            <div className="mt-8 flex items-center justify-between text-sm text-[var(--slate)]">
              <button
                type="button"
                data-testid="blog-prev-button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="rounded-full border border-[var(--line)] bg-white px-4 py-1.5 font-medium transition-colors hover:border-[var(--slate)]/30 disabled:opacity-40"
              >
                ← Newer
              </button>
              <span className="font-[family-name:var(--font-mono)] text-xs tabular-nums">
                {page} / {lastPage}
              </span>
              <button
                type="button"
                data-testid="blog-next-button"
                onClick={() => setPage((p) => Math.min(lastPage, p + 1))}
                disabled={page >= lastPage}
                className="rounded-full border border-[var(--line)] bg-white px-4 py-1.5 font-medium transition-colors hover:border-[var(--slate)]/30 disabled:opacity-40"
              >
                Older →
              </button>
            </div>
          )}
        </section>
      </main>

      <MarketingFooter />
    </div>
  );
}
