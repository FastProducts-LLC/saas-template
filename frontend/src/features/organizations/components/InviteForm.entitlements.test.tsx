import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it } from "vitest";
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
import InviteForm from "./InviteForm";
import { errorCatalog } from "../../../shared/api/errorCatalog";
function setup(limit: number | null = 5, used = 3, rejected = false) {
  const fetch = mockFetch().mockImplementation((url: string, init?: RequestInit) => {
    if (init?.method === "POST")
      return Promise.resolve(
        rejected ? jsonResponse(403, { code: "ERR_ENT_002" }) : jsonResponse(200, { id: "i1" }),
      );
    if (url.endsWith("/entitlements"))
      return Promise.resolve(
        jsonResponse(200, {
          plan: "free",
          entitlements: [
            { key: "seats", limit, used, source: "plan", included: true, expires_at: null },
          ],
        }),
      );
    return Promise.resolve(jsonResponse(200, []));
  });
  const client = mount(<InviteForm orgId="o1" />);
  return { fetch, client };
}
it("shows seat usage", async () => {
  setup();
  expect(await screen.findByText("3 of 5 seats used")).toBeInTheDocument();
});
it("disables inviting and shows the upgrade prompt at the seat limit", async () => {
  const { fetch } = setup(5, 5);
  await screen.findByText("5 of 5 seats used");
  expect(screen.getByRole("button", { name: "Invite" })).toBeDisabled();
  expect(screen.getByRole("link", { name: /Upgrade/ })).toBeInTheDocument();
  fireEvent.submit(screen.getByTestId("invite-form"));
  expect(fetch.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
});
it("allows inviting when seats are unlimited", async () => {
  const { fetch, client } = setup(null, 30);
  await screen.findByText("30 of Unlimited seats used");
  expect(screen.getByRole("button", { name: "Invite" })).toBeEnabled();
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "person@example.com" } });
  fireEvent.click(screen.getByRole("button", { name: "Invite" }));
  await waitFor(() =>
    expect(fetch.mock.calls.filter(([url]) => String(url).endsWith("/entitlements"))).toHaveLength(
      2,
    ),
  );
  expect(client.getQueryState(["entitlements", "o1"])?.isInvalidated).toBe(false);
});
it("shows the server limit error when the invite is rejected", async () => {
  setup(5, 3, true);
  await screen.findByText("3 of 5 seats used");
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "person@example.com" } });
  fireEvent.click(screen.getByRole("button", { name: "Invite" }));
  const alert = await screen.findByTestId("invite-error");
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
    if (init?.method === "POST") return Promise.resolve(jsonResponse(200, { id: "i1" }));
    return Promise.resolve(jsonResponse(200, []));
  });
  mount(<InviteForm orgId="o1" />);
  expect(screen.getByLabelText("Email")).toBeEnabled();
  expect(screen.getByRole("button", { name: "Invite" })).toBeEnabled();
  failEntitlements(jsonResponse(403, { code: "ERR_PERM_001" }));
  await screen.findByText("Unable to load seat usage.");
  expect(screen.getByLabelText("Role")).toBeEnabled();
  expect(screen.getByRole("button", { name: "Invite" })).toBeEnabled();
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "person@example.com" } });
  fireEvent.click(screen.getByRole("button", { name: "Invite" }));
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(
        ([url, init]) => url === "/api/orgs/o1/invitations" && init?.method === "POST",
      ),
    ).toBe(true),
  );
  await waitFor(() => expect(screen.getByLabelText("Email")).toHaveValue(""));
});
