import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
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
import ApiKeysPage from "./ApiKeysPage";
import { errorCatalog } from "../../../shared/api/errorCatalog";
vi.mock("../../organizations", () => ({
  useOrg: () => ({ currentOrg: { id: "o1", role: "owner" } }),
}));
function setup(limit = 5, used = 3) {
  const fetch = mockFetch().mockImplementation((url: string, init?: RequestInit) => {
    if (init?.method === "POST") return Promise.resolve(jsonResponse(403, { code: "ERR_ENT_002" }));
    return Promise.resolve(
      jsonResponse(
        200,
        url.endsWith("/entitlements")
          ? {
              plan: "free",
              entitlements: [
                { key: "api_keys", limit, used, source: "plan", included: true, expires_at: null },
              ],
            }
          : [],
      ),
    );
  });
  mount(<ApiKeysPage />);
  return fetch;
}
it("shows API key usage", async () => {
  setup();
  expect(await screen.findByText("3 of 5 API keys used")).toBeInTheDocument();
});
it("disables key creation at the limit", async () => {
  const fetch = setup(5, 5);
  await screen.findByText("5 of 5 API keys used");
  expect(screen.getByTestId("api-keys-create-button")).toBeDisabled();
  expect(screen.getByRole("link", { name: /Upgrade/ })).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("api-keys-create-button"));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(fetch.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
});
it("shows the server limit error when creation is rejected", async () => {
  setup();
  await screen.findByText("3 of 5 API keys used");
  fireEvent.click(screen.getByTestId("api-keys-create-button"));
  fireEvent.change(screen.getByLabelText("Key name"), { target: { value: "Production" } });
  fireEvent.click(screen.getByTestId("api-keys-create-confirm"));
  const alert = await screen.findByTestId("api-keys-error");
  expect(alert).toHaveTextContent(errorCatalog.ERR_ENT_002.message);
  expect(alert).toHaveTextContent(errorCatalog.ERR_ENT_002.action);
});

it("keeps the form usable when entitlements fail to load", async () => {
  let failEntitlements!: (response: Response) => void;
  const failure = new Promise<Response>((resolve) => {
    failEntitlements = resolve;
  });
  const fetch = mockFetch().mockImplementation((url: string, init?: RequestInit) => {
    if (url.endsWith("/entitlements")) return failure;
    if (init?.method === "POST")
      return Promise.resolve(jsonResponse(200, { id: "k1", raw_key: "test-secret" }));
    return Promise.resolve(jsonResponse(200, []));
  });
  mount(<ApiKeysPage />);
  expect(screen.getByTestId("api-keys-create-button")).toBeEnabled();
  fireEvent.click(screen.getByTestId("api-keys-create-button"));
  fireEvent.change(screen.getByLabelText("Key name"), { target: { value: "Production" } });
  expect(screen.getByTestId("api-keys-create-confirm")).toBeEnabled();
  failEntitlements(jsonResponse(403, { code: "ERR_PERM_001" }));
  await screen.findByText("Unable to load API key usage.");
  expect(screen.getByTestId("api-keys-create-confirm")).toBeEnabled();
  fireEvent.click(screen.getByTestId("api-keys-create-confirm"));
  await waitFor(() =>
    expect(fetch.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true),
  );
  expect(await screen.findByTestId("api-keys-secret")).toHaveTextContent("test-secret");
});
