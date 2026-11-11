import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it } from "vitest";
import type { ReactNode } from "react";
import { jsonResponse, mockFetch, restoreFetch } from "../../test/fetchMock";
function mount(ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}
afterEach(() => {
  cleanup();
  restoreFetch();
});
import { errorCatalog } from "../../shared/api/errorCatalog";
import AdminRevenuePage from "./AdminRevenuePage";
import { formatMoney } from "../../shared/lib/money";
const revenue = {
  currency: "usd",
  mrr_cents: 12345,
  arr_cents: 148140,
  active: 7,
  trialing: 2,
  past_due: 1,
  canceling: 3,
  new_last_30d: 4,
  canceled_last_30d: 5,
  computed_at: "2026-11-09T00:00:00Z",
  by_plan: [{ plan: "pro", interval: "monthly", count: 7, mrr_cents: 12345 }],
};
it("renders MRR, ARR and subscription counts", async () => {
  mockFetch().mockResolvedValue(jsonResponse(200, revenue));
  mount(<AdminRevenuePage />);
  await screen.findByText("Revenue");
  for (const [label, value] of [
    ["MRR", formatMoney(12345)],
    ["ARR", formatMoney(148140)],
    ["Active", "7"],
    ["Trialing", "2"],
    ["Past due", "1"],
    ["Canceling", "3"],
    ["New in the last 30 days", "4"],
    ["Canceled in the last 30 days", "5"],
  ])
    expect(screen.getByText(label, { selector: "dt" }).parentElement).toHaveTextContent(value);
});
it("renders the per-plan breakdown", async () => {
  mockFetch().mockResolvedValue(jsonResponse(200, revenue));
  mount(<AdminRevenuePage />);
  const table = await screen.findByRole("table");
  const row = within(table).getByText("pro").closest("tr")!;
  expect(row).toHaveTextContent("monthly");
  expect(row).toHaveTextContent("7");
  expect(row).toHaveTextContent(formatMoney(12345));
});
it("shows an empty state when there are no subscriptions", async () => {
  mockFetch().mockResolvedValue(
    jsonResponse(200, {
      ...revenue,
      mrr_cents: 0,
      arr_cents: 0,
      active: 0,
      trialing: 0,
      past_due: 0,
      canceling: 0,
      new_last_30d: 0,
      canceled_last_30d: 0,
      by_plan: [],
    }),
  );
  mount(<AdminRevenuePage />);
  expect(await screen.findByText("There are no subscriptions yet.")).toBeInTheDocument();
});
it("shows an error state when the request fails", async () => {
  mockFetch().mockResolvedValue(jsonResponse(403, { detail: "Revenue unavailable" }));
  mount(<AdminRevenuePage />);
  expect(await screen.findByRole("alert")).toHaveTextContent(errorCatalog.ERR_PERM_001.message);
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});
