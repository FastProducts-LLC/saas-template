import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import BlogListPage from "./BlogListPage";
import * as endpoints from "../api/endpoints";

vi.mock("../api/endpoints", () => ({
  listPublishedPosts: vi.fn(),
  listTags: vi.fn(),
}));

// The marketing chrome pulls in auth/consent contexts — not under test here.
vi.mock("../../home", () => ({
  MarketingHeader: () => null,
  MarketingFooter: () => null,
}));

const post = {
  id: "11111111-1111-1111-1111-111111111111",
  title: "Launch Notes",
  slug: "launch-notes",
  excerpt: "What shipped this week.",
  cover_image: null,
  published_at: "2026-08-01T12:00:00Z",
  tags: ["product"],
};

function renderPage(initialEntry = "/blog") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <BlogListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe("public blog list", () => {
  it("renders published post cards linking to the article", async () => {
    vi.mocked(endpoints.listPublishedPosts).mockResolvedValue({
      items: [post],
      total: 1,
      page: 1,
      page_size: 10,
    });
    vi.mocked(endpoints.listTags).mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText("Launch Notes")).toBeInTheDocument();
    expect(screen.getByText("What shipped this week.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Launch Notes" })).toHaveAttribute(
      "href",
      "/blog/launch-notes",
    );
    expect(screen.getByTestId("blog-post-tag")).toHaveTextContent("#product");
  });

  it("shows the empty state when nothing is published", async () => {
    vi.mocked(endpoints.listPublishedPosts).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 10,
    });
    vi.mocked(endpoints.listTags).mockResolvedValue([]);

    renderPage();

    expect(await screen.findByTestId("blog-empty-state")).toBeInTheDocument();
  });

  it("debounces search input into listPublishedPosts q", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(endpoints.listPublishedPosts).mockResolvedValue({
      items: [post],
      total: 1,
      page: 1,
      page_size: 10,
    });
    vi.mocked(endpoints.listTags).mockResolvedValue([]);

    renderPage();
    await screen.findByText("Launch Notes");

    fireEvent.change(screen.getByTestId("blog-search-input"), {
      target: { value: "launch" },
    });

    await act(async () => {
      vi.advanceTimersByTime(300);
    });

    await waitFor(() =>
      expect(endpoints.listPublishedPosts).toHaveBeenCalledWith(
        1,
        expect.any(Number),
        expect.objectContaining({ q: "launch" }),
      ),
    );
  });

  it("shows no-results when a search returns empty", async () => {
    vi.mocked(endpoints.listPublishedPosts).mockImplementation(async (_page, _size, opts) => {
      if (opts?.q) {
        return { items: [], total: 0, page: 1, page_size: 10 };
      }
      return { items: [post], total: 1, page: 1, page_size: 10 };
    });
    vi.mocked(endpoints.listTags).mockResolvedValue([]);

    renderPage();
    await screen.findByText("Launch Notes");

    fireEvent.change(screen.getByTestId("blog-search-input"), {
      target: { value: "zzzz" },
    });

    expect(await screen.findByTestId("blog-no-results")).toBeInTheDocument();
    expect(screen.queryByTestId("blog-empty-state")).not.toBeInTheDocument();
  });
});
