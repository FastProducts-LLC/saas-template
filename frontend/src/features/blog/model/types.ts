import type { PostStatus } from "../../../shared/api/enums";
import { BLOG_MAX_TAGS, BLOG_TAG_MAX_LENGTH } from "../../../shared/lib/policy";

export type { PostStatus };

/** Public list card — published posts only, no body. */
export interface BlogPostSummary {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  cover_image: string | null;
  published_at: string | null;
  tags: string[];
}

/** Public article detail. */
export interface BlogPost extends BlogPostSummary {
  content: string;
  meta_title: string | null;
  meta_description: string | null;
  updated_at: string;
  author_name: string | null;
  related: BlogPostSummary[];
}

/** Full post as seen in the admin console — any status. */
export interface AdminBlogPost extends BlogPostSummary {
  content: string;
  meta_title: string | null;
  meta_description: string | null;
  updated_at: string;
  status: PostStatus;
  author_id: string | null;
  view_count: number;
  created_at: string;
}

export interface BlogPostPayload {
  title: string;
  slug?: string | null;
  excerpt: string;
  content: string;
  cover_image?: string | null;
  meta_title?: string | null;
  meta_description?: string | null;
  status?: PostStatus;
  /** ISO go-live time when status is "scheduled". */
  scheduled_for?: string;
  tags?: string[];
}

/** Tag + published-post count from GET /blog/tags. */
export interface BlogTagCount {
  tag: string;
  count: number;
}

/** Structurally identical to the backend page envelope (and admin's Page<T>). */
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/** Client-side mirror of blog/domain/services.slugify — for live slug preview. */
export function slugify(title: string): string {
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80)
    .replace(/-+$/, "");
  return slug || "post";
}

/**
 * Client-side mirror of blog/domain/services.normalize_tags — for live chip
 * preview and normalize-before-save in the admin editor.
 */
export function parseTagsInput(raw: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of raw.split(",")) {
    let tag = part
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
    tag = tag.slice(0, BLOG_TAG_MAX_LENGTH).replace(/-+$/, "");
    if (!tag || seen.has(tag)) continue;
    seen.add(tag);
    out.push(tag);
    if (out.length >= BLOG_MAX_TAGS) break;
  }
  return out;
}

export function formatPostDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export type GenerationJobStatus = "pending" | "succeeded" | "failed";
export type LlmProvider = "anthropic" | "openai" | "gemini";

export interface GenerationJob {
  id: string;
  status: GenerationJobStatus;
  error: string | null;
  post_id: string | null;
  topic: string;
  created_at: string;
}

export interface DraftGeneratePayload {
  topic: string;
  keywords?: string[];
  notes?: string | null;
  provider?: LlmProvider;
}
