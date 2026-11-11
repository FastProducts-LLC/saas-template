import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CreditBalanceBadge } from "./CreditBalanceBadge";
import { creditsKeys } from "../api/keys";
import type { Wallet } from "../model/types";

const ORG_ID = "org-1";

function makeWallet(balance: number): Wallet {
  return {
    balance,
    reserved: 0,
    monthly_allowance: 0,
    allowance_period: null,
    pending_holds: [],
  };
}

function renderWithClient(client: QueryClient) {
  return render(
    <QueryClientProvider client={client}>
      <CreditBalanceBadge orgId={ORG_ID} />
    </QueryClientProvider>,
  );
}

describe("CreditBalanceBadge", () => {
  it("renders the formatted balance when the wallet is seeded", () => {
    const client = new QueryClient();
    // Seed the exact key the useWallet hook reads from so it resolves without a fetch.
    client.setQueryData(creditsKeys.wallet(ORG_ID), makeWallet(12500));

    renderWithClient(client);

    expect(screen.getByText("12,500")).toBeInTheDocument();
  });

  it("renders nothing when there is no wallet data", () => {
    const client = new QueryClient({
      defaultOptions: { queries: { enabled: false } },
    });

    const { container } = renderWithClient(client);

    expect(container).toBeEmptyDOMElement();
  });
});
