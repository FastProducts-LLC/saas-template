import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import AdminCustomersPage from "./AdminCustomersPage";
import { listCustomers } from "./api";

vi.mock("./api", () => ({
  listCustomers: vi.fn(),
  mergeOrgs: vi.fn(),
}));

const customer = {
  organization_id: "11111111-1111-1111-1111-111111111111",
  organization_name: "Search Co",
  organization_slug: "search-co",
  created_at: "2026-07-09T12:00:00Z",
  suspended_at: null,
  member_count: 1,
  owner_email: "owner@example.com",
  owner_name: "Ada Admin",
  credits_spent: 6,
  credit_balance: 9,
  dollars_spent_cents: 600,
  dollar_balance_cents: 900,
};

function renderRoute(ui: React.ReactNode, path: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("admin customers", () => {
  it("lists each customer with owner and credit spend", async () => {
    vi.mocked(listCustomers).mockResolvedValue({
      items: [customer],
      total: 1,
      page: 1,
      page_size: 25,
    });

    renderRoute(<AdminCustomersPage />, "/admin/customers");

    expect(await screen.findByText("Search Co")).toBeInTheDocument();
    expect(screen.getByText("Ada Admin")).toBeInTheDocument();
    expect(screen.getByText("owner@example.com")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
    expect(screen.getByText("9")).toBeInTheDocument();
  });
});
