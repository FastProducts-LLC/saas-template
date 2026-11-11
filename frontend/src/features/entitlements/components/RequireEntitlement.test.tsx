import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { jsonResponse, mockFetch, restoreFetch } from "../../../test/fetchMock";
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
import RequireEntitlement from "./RequireEntitlement";
import { ROUTES } from "../../../shared/lib/routes";
vi.mock("../../organizations", () => ({ useOrg: () => ({ currentOrg: { id: "o1" } }) }));
function setup(limit: number | null) {
  mockFetch().mockResolvedValue(
    jsonResponse(200, {
      plan: "free",
      entitlements: [
        { key: "seats", limit, used: 0, source: "plan", included: limit !== 0, expires_at: null },
      ],
    }),
  );
  mount(
    <RequireEntitlement entitlement="seats">
      <p>Included content</p>
    </RequireEntitlement>,
  );
}
it("renders children when the entitlement is included", async () => {
  setup(null);
  expect(await screen.findByText("Included content")).toBeInTheDocument();
});
it("renders the upgrade prompt when the limit is zero", async () => {
  setup(0);
  expect(await screen.findByRole("alert")).toHaveTextContent("Not included");
  expect(screen.queryByText("Included content")).not.toBeInTheDocument();
});
it("links the upgrade prompt to billing", async () => {
  setup(0);
  expect(await screen.findByRole("link", { name: /Upgrade/ })).toHaveAttribute(
    "href",
    ROUTES.billing,
  );
});
it("renders nothing misleading while entitlements are loading", () => {
  mockFetch().mockImplementation(() => new Promise(() => {}));
  mount(<RequireEntitlement entitlement="seats">Included content</RequireEntitlement>);
  expect(screen.getByRole("status")).toHaveTextContent("Loading");
  expect(screen.queryByText("Included content")).not.toBeInTheDocument();
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});
