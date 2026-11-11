import { api } from "../../../shared/api";
import type {
  AdminBlogPost,
  BlogPost,
  BlogPostPayload,
  BlogPostSummary,
  BlogTagCount,
  DraftGeneratePayload,
  GenerationJob,
  Page,
  PostStatus,
} from "../model/types";

export const listPublishedPosts = (
  page: number,
  pageSize: number,
  opts?: { q?: string; tag?: string },
) => {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (opts?.q) params.set("q", opts.q);
  if (opts?.tag) params.set("tag", opts.tag);
  return api<Page<BlogPostSummary>>(`/blog/posts?${params}`);
};

export const listTags = () => api<BlogTagCount[]>("/blog/tags");

export const getPublishedPost = (slug: string) =>
  api<BlogPost>(`/blog/posts/${encodeURIComponent(slug)}`);

export const getPreviewPost = (token: string) =>
  api<BlogPost>(`/blog/preview?token=${encodeURIComponent(token)}`);

export type PreviewLink = {
  token: string;
  url: string;
  expires_in_days: number;
};

export const createPreviewLink = (postId: string) =>
  api<PreviewLink>(`/admin/blog/posts/${postId}/preview-link`, { method: "POST" });

export const listAdminPosts = (status: PostStatus | "", page: number) =>
  api<Page<AdminBlogPost>>(`/admin/blog/posts?page=${page}${status ? `&status=${status}` : ""}`);

export const getAdminPost = (postId: string) => api<AdminBlogPost>(`/admin/blog/posts/${postId}`);

export const createPost = (payload: BlogPostPayload) =>
  api<AdminBlogPost>("/admin/blog/posts", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const updatePost = (postId: string, payload: Partial<BlogPostPayload>) =>
  api<AdminBlogPost>(`/admin/blog/posts/${postId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

export const deletePost = (postId: string) =>
  api<void>(`/admin/blog/posts/${postId}`, { method: "DELETE" });

export const requestDraftGeneration = (payload: DraftGeneratePayload) =>
  api<GenerationJob>("/admin/blog/generate", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const getGenerationJob = (jobId: string) =>
  api<GenerationJob>(`/admin/blog/generate/${jobId}`);
