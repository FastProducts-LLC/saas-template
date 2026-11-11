import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import BlogPreviewPage from "./BlogPreviewPage";
import * as endpoints from "../api/endpoints";
import type { BlogPost } from "../model/types";

vi.mock("../api/endpoints", () => ({
  getPreviewPost: vi.fn(),
}));

vi.mock("../../home", () => ({
  MarketingHeader: () => null,
  MarketingFooter: () => null,
}));

const draftPost: BlogPost = {
  id: "11111111-1111-1111-1111-111111111111",
  title: "Secret Draft",
  slug: "secret-draft",
  excerpt: "Not ready.",
  cover_image: null,
  published_at: null,
  tags: [],
  content: "## Coming soon",
  meta_title: null,
  meta_description: null,
  updated_at: "2026-08-01T12:00:00Z",
  author_name: "Test User",
  related: [],
};

function renderPage(entry = "/blog/preview?token=abc") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <BlogPreviewPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("BlogPreviewPage", () => {
  it("renders draft banner and title for a valid token", async () => {
    vi.mocked(endpoints.getPreviewPost).mockResolvedValue(draftPost);

    renderPage();

    expect(await screen.findByTestId("blog-preview-banner")).toHaveTextContent(
      "Draft preview — this post is not published.",
    );
    expect(screen.getByText("Secret Draft")).toBeInTheDocument();
  });

  it("shows invalid state when the preview fetch rejects", async () => {
    vi.mocked(endpoints.getPreviewPost).mockRejectedValue(new Error("404"));

    renderPage();

    expect(await screen.findByTestId("blog-preview-not-found")).toHaveTextContent(
      "Preview link is invalid or expired",
    );
    expect(screen.getByRole("link", { name: /Back to the blog/i })).toHaveAttribute(
      "href",
      "/blog",
    );
  });
});
