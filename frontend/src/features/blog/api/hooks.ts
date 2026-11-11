import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { BLOG_PAGE_SIZE } from "../../../shared/lib/policy";
import * as endpoints from "./endpoints";
import { blogKeys } from "./keys";
import type { BlogPostPayload, DraftGeneratePayload, PostStatus } from "../model/types";

export function usePublishedPosts(page: number, q = "", tag = "") {
  return useQuery({
    queryKey: blogKeys.publicList(page, q, tag),
    queryFn: () =>
      endpoints.listPublishedPosts(page, BLOG_PAGE_SIZE, {
        q: q || undefined,
        tag: tag || undefined,
      }),
  });
}

export function useBlogTags() {
  return useQuery({
    queryKey: blogKeys.tags(),
    queryFn: () => endpoints.listTags(),
  });
}

export function usePublishedPost(slug: string) {
  return useQuery({
    queryKey: blogKeys.publicPost(slug),
    queryFn: () => endpoints.getPublishedPost(slug),
    retry: false,
  });
}

export function usePreviewPost(token: string) {
  return useQuery({
    queryKey: blogKeys.previewPost(token),
    queryFn: () => endpoints.getPreviewPost(token),
    enabled: Boolean(token),
    retry: false,
  });
}

export function useAdminPosts(status: PostStatus | "", page: number) {
  return useQuery({
    queryKey: blogKeys.adminList(status, page),
    queryFn: () => endpoints.listAdminPosts(status, page),
  });
}

export function useAdminPost(postId: string | undefined) {
  return useQuery({
    queryKey: blogKeys.adminPost(postId ?? ""),
    queryFn: () => endpoints.getAdminPost(postId!),
    enabled: Boolean(postId),
  });
}

export function useCreatePost() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BlogPostPayload) => endpoints.createPost(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: blogKeys.all }),
  });
}

export function useUpdatePost(postId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<BlogPostPayload>) => endpoints.updatePost(postId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: blogKeys.all }),
  });
}

export function useDeletePost() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (postId: string) => endpoints.deletePost(postId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: blogKeys.all }),
  });
}

export function useRequestDraftGeneration() {
  return useMutation({
    mutationFn: (payload: DraftGeneratePayload) => endpoints.requestDraftGeneration(payload),
  });
}

export function useGenerationJob(jobId: string | undefined, opts?: { enabled?: boolean }) {
  return useQuery({
    queryKey: blogKeys.generationJob(jobId ?? ""),
    queryFn: () => endpoints.getGenerationJob(jobId!),
    enabled: Boolean(jobId) && (opts?.enabled ?? true),
    refetchInterval: (q) => (q.state.data?.status === "pending" ? 2000 : false),
  });
}
