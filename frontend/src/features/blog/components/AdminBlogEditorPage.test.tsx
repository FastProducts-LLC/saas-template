import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import AdminBlogEditorPage from "./AdminBlogEditorPage";
import * as endpoints from "../api/endpoints";
import type { AdminBlogPost, PostStatus } from "../model/types";

vi.mock("../api/endpoints", () => ({
  getAdminPost: vi.fn(),
  updatePost: vi.fn(),
  createPost: vi.fn(),
  deletePost: vi.fn(),
  createPreviewLink: vi.fn(),
}));

const draftPost: AdminBlogPost = {
  id: "11111111-1111-1111-1111-111111111111",
  title: "Draft Piece",
  slug: "draft-piece",
  excerpt: "Not ready yet.",
  content: "## Body",
  cover_image: null,
  published_at: null,
  tags: [],
  meta_title: null,
  meta_description: null,
  updated_at: "2026-08-01T12:00:00Z",
  status: "draft" as PostStatus,
  author_id: null,
  view_count: 0,
  created_at: "2026-08-01T12:00:00Z",
};

function renderEditor(postId = draftPost.id) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/admin/blog/${postId}`]}>
        <Routes>
          <Route path="/admin/blog/:id" element={<AdminBlogEditorPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AdminBlogEditorPage schedule controls", () => {
  it("shows Schedule input and button for a draft post", async () => {
    vi.mocked(endpoints.getAdminPost).mockResolvedValue(draftPost);

    renderEditor();

    expect(await screen.findByTestId("admin-blog-schedule-input")).toBeInTheDocument();
    expect(screen.getByTestId("admin-blog-schedule-button")).toBeInTheDocument();
    expect(screen.getByTestId("admin-blog-schedule-button")).toBeDisabled();
    expect(screen.getByTestId("admin-blog-publish-button")).toBeInTheDocument();
  });
});
