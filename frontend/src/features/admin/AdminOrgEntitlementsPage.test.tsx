import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { afterEach, expect, it } from "vitest";
import { jsonResponse, mockFetch, restoreFetch } from "../../test/fetchMock";
afterEach(() => {
  cleanup();
  restoreFetch();
});
import AdminOrgEntitlementsPage from "./AdminOrgEntitlementsPage";
import { ROUTES, ROUTE_PATTERNS } from "../../shared/lib/routes";
const snapshot = {
  plan: "pro",
  entitlements: [
    { key: "seats", limit: 9, used: 3, source: "override", included: true, expires_at: null },
    { key: "api_keys", limit: null, used: 2, source: "plan", included: true, expires_at: null },
  ],
  overrides: [
    {
      key: "seats",
      limit_value: 9,
      note: null,
      expires_at: null,
      created_by_id: null,
      updated_at: "2026-11-09T00:00:00Z",
    },
  ],
};
function setup(fields?: Record<string, string>) {
  const fetch = mockFetch().mockImplementation((_url: string, init?: RequestInit) =>
    Promise.resolve(
      init?.method === "PUT"
        ? fields
          ? jsonResponse(422, { code: "ERR_VALIDATION", fields, detail: "Invalid override" })
          : jsonResponse(200, {})
        : init?.method === "DELETE"
          ? jsonResponse(204)
          : jsonResponse(200, snapshot),
    ),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[ROUTES.admin.orgEntitlements("o1")]}>
        <Routes>
          <Route
            path={ROUTE_PATTERNS.admin.orgEntitlements}
            element={<AdminOrgEntitlementsPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetch;
}
async function edit() {
  fireEvent.click(await screen.findByRole("button", { name: "Set override for seats" }));
}
it("lists each entitlement with limit, usage and source", async () => {
  setup();
  const table = await screen.findByRole("table");
  expect(screen.getByText("pro")).toBeInTheDocument();
  const seats = within(table).getByText("seats").closest("tr")!;
  expect(seats).toHaveTextContent("9");
  expect(seats).toHaveTextContent("3");
  expect(seats).toHaveTextContent("override");
  const keys = within(table).getByText("api_keys").closest("tr")!;
  expect(keys).toHaveTextContent("Unlimited");
  expect(keys).toHaveTextContent("2");
  expect(keys).toHaveTextContent("plan");
});
it("sets a numeric override", async () => {
  const fetch = setup();
  await edit();
  fireEvent.change(screen.getByLabelText("Limit"), { target: { value: "12" } });
  fireEvent.change(screen.getByLabelText("Note (optional)"), {
    target: { value: "Capacity adjustment" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save override" }));
  await screen.findByText("Override saved.");
  const call = fetch.mock.calls.find(([, init]) => init?.method === "PUT")!;
  expect(call[0]).toBe("/api/admin/organizations/o1/entitlements/seats");
  expect(JSON.parse(call[1].body)).toEqual({
    limit_value: 12,
    expires_at: null,
    note: "Capacity adjustment",
  });
  expect(
    fetch.mock.calls.filter(([, init]) => !init?.method || init.method === "GET"),
  ).toHaveLength(2);
});
it("sets an unlimited override", async () => {
  const fetch = setup();
  await edit();
  fireEvent.click(screen.getByLabelText("Unlimited"));
  fireEvent.click(screen.getByRole("button", { name: "Save override" }));
  await screen.findByText("Override saved.");
  expect(
    JSON.parse(fetch.mock.calls.find(([, init]) => init?.method === "PUT")![1].body).limit_value,
  ).toBeNull();
});
it("rejects a negative limit before submitting", async () => {
  const fetch = setup();
  await edit();
  fireEvent.change(screen.getByLabelText("Limit"), { target: { value: "-1" } });
  fireEvent.click(screen.getByRole("button", { name: "Save override" }));
  expect(await screen.findByText("Enter a non-negative integer.")).toBeInTheDocument();
  expect(fetch.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(false);
});
it("rejects a past expiry before submitting", async () => {
  const fetch = setup();
  await edit();
  fireEvent.change(screen.getByLabelText("Expiry (optional)"), {
    target: { value: "2000-01-01T12:00" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save override" }));
  expect(await screen.findByText("Expiry must be in the future.")).toBeInTheDocument();
  expect(fetch.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(false);
});
it("removes an override after confirmation", async () => {
  const fetch = setup();
  fireEvent.click(await screen.findByRole("button", { name: "Remove override for seats" }));
  expect(fetch.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false);
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", { name: "Confirm removal" }),
  );
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(fetch.mock.calls.find(([, init]) => init?.method === "DELETE")![0]).toBe(
    "/api/admin/organizations/o1/entitlements/seats",
  );
});
it("maps server validation errors onto fields", async () => {
  setup({ limit_value: "Limit rejected", expires_at: "Expiry rejected", note: "Note rejected" });
  await edit();
  fireEvent.click(screen.getByRole("button", { name: "Save override" }));
  await screen.findByText("Limit rejected");
  for (const label of ["Limit", "Expiry (optional)", "Note (optional)"])
    expect(screen.getByLabelText(label)).toHaveAttribute("aria-invalid", "true");
  expect(screen.getByText("Expiry rejected")).toBeInTheDocument();
  expect(screen.getByText("Note rejected")).toBeInTheDocument();
});
