import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { type ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { jsonResponse, mockFetch, restoreFetch } from "../../test/fetchMock";
import AdminOverviewPage from "./AdminOverviewPage";

function renderWithProviders(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

function makeSeries(counts: number[]) {
  return counts.map((count, index) => ({
    date: `2026-06-${String(index + 1).padStart(2, "0")}`,
    count,
  }));
}

describe("AdminOverviewPage", () => {
  beforeEach(() => {
    const fetchMock = mockFetch();
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/admin/stats") {
        return jsonResponse(200, {
          total_users: 10,
          active_users: 8,
          total_organizations: 4,
        });
      }
      if (url === "/api/admin/analytics") {
        return jsonResponse(200, {
          user_signups: makeSeries([0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2]),
          org_signups: makeSeries([0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]),
          credits_spent_daily: makeSeries([
            0, 0, 0, 0, 0, 0, 0, 3, 3, 3, 3, 3, 3, 3, 5, 5, 5, 5, 5, 5, 5,
          ]),
          generations_by_status: [
            { label: "succeeded", count: 18 },
            { label: "failed", count: 2 },
            { label: "pending", count: 1 },
          ],
          generations_by_kind: [
            { label: "image_gpt", count: 12 },
            { label: "llm_call", count: 9 },
          ],
          top_customers_by_credits: [
            { name: "Acme", value: 40 },
            { name: "Globex", value: 10 },
          ],
          credit_summary: {
            total_balance: 25,
            total_pending_holds: 2,
            total_credits_captured: 100,
          },
          commercial_summary: {
            organizations_with_billing_account: 2,
            organizations_with_wallet: 3,
            negative_wallets: 1,
            zero_balance_wallets: 1,
            low_balance_wallets: 1,
            low_balance_threshold: 10,
          },
          operations_summary: {
            pending_invitations: 4,
            expired_invitations: 1,
            open_privacy_requests: 2,
            overdue_privacy_requests: 1,
            privacy_requests_due_soon: 1,
            stale_pending_generations: 1,
            expired_credit_holds: 1,
          },
          security_summary: {
            superusers: 1,
            email_verified_users: 7,
            unverified_users: 1,
            email_suppressed_users: 1,
            active_api_keys: 5,
            api_keys_used_30d: 3,
            stale_api_keys: 1,
            unused_api_keys: 2,
          },
          recent_admin_actions: [
            { label: "credits.adjust", count: 3 },
            { label: "user.deactivate", count: 1 },
          ],
        });
      }
      return jsonResponse(404, {});
    });
  });

  afterEach(() => {
    cleanup();
    restoreFetch();
  });

  it("renders derived SaaS-critical overview signals", async () => {
    renderWithProviders(<AdminOverviewPage />);

    expect(await screen.findByText("Activation rate")).toBeInTheDocument();
    expect(
      await within(screen.getByTestId("admin-overview-activation-rate")).findByText("80%"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("admin-overview-tenant-density")).getByText("2.5"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("admin-overview-generation-failure-rate")).getByText("9.5%"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("admin-overview-customer-concentration")).getByText("50%"),
    ).toBeInTheDocument();

    expect(screen.getByTestId("admin-overview-critical-signals")).toBeInTheDocument();
    expect(screen.getByTestId("admin-overview-generation-mix")).toHaveTextContent("GPT images");
    expect(screen.getByTestId("admin-overview-credit-exposure")).toHaveTextContent(
      "Credit settlement",
    );
    expect(screen.getByTestId("admin-overview-workflows")).toHaveTextContent("Privacy requests");
    expect(screen.getByTestId("admin-overview-operations-backlog")).toHaveTextContent(
      "Overdue privacy requests",
    );
    expect(screen.getByTestId("admin-overview-security-posture")).toHaveTextContent(
      "Stale API keys",
    );
    expect(screen.getByTestId("admin-overview-commercial-risk")).toHaveTextContent(
      "Negative wallets",
    );
    expect(screen.getByTestId("admin-overview-recent-actions")).toHaveTextContent("credits.adjust");
  });
});
