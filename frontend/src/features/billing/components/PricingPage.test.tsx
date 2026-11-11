import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as endpoints from "../api/endpoints";
import { ROUTES } from "../../../shared/lib/routes";
import { formatMoney } from "../../../shared/lib/money";
import PricingPage from "./PricingPage";
import { formatPlanPrice } from "../model/format";

vi.mock("../api/endpoints");
const auth = vi.hoisted(() => ({ user: null as null | { id: string } }));
vi.mock("../../auth", () => ({ useAuth: () => auth }));
vi.mock("../../home", () => ({ MarketingHeader: () => null, MarketingFooter: () => null }));
vi.mock("../../credits", () => ({
  useCreditPacks: () => ({ data: [] }),
  PackGrid: () => null,
  PackDiscountStamp: () => null,
}));
const plans = [
  {
    plan: "free" as const,
    name: "Free",
    monthly_price_cents: 0,
    annual_price_cents: 0,
    monthly_credits: 10,
    purchasable: { monthly: false, annual: false },
  },
  {
    plan: "pro" as const,
    name: "Pro",
    monthly_price_cents: 1700,
    annual_price_cents: 17000,
    monthly_credits: 100,
    purchasable: { monthly: true, annual: true },
  },
  {
    plan: "team" as const,
    name: "Team",
    monthly_price_cents: 4900,
    annual_price_cents: 49000,
    monthly_credits: 500,
    purchasable: { monthly: true, annual: true },
  },
];
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PricingPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  vi.clearAllMocks();
  auth.user = null;
  vi.mocked(endpoints.listPlans).mockResolvedValue(plans);
});
afterEach(cleanup);
it("renders a card for every plan with its price", async () => {
  mount();
  for (const plan of plans) {
    const card = await screen.findByRole("article", { name: `${plan.name} plan` });
    expect(
      within(card).getByText(formatPlanPrice(plan.monthly_price_cents), { exact: false }),
    ).toBeInTheDocument();
    expect(within(card).getByText(plan.monthly_credits.toLocaleString())).toBeInTheDocument();
  }
});
it("switches prices when the annual interval is selected", async () => {
  mount();
  await screen.findByRole("article", { name: "Pro plan" });
  fireEvent.click(screen.getByRole("radio", { name: "Annual" }));
  expect(screen.getByRole("radio", { name: "Annual" })).toBeChecked();
  for (const plan of plans) {
    expect(
      within(screen.getByRole("article", { name: `${plan.name} plan` })).getByText(
        formatPlanPrice(plan.annual_price_cents),
        { exact: false },
      ),
    ).toBeInTheDocument();
  }
});
it("shows the annual saving computed from API prices", async () => {
  // Deliberately irregular catalog values catch hardcoded savings.
  vi.mocked(endpoints.listPlans).mockResolvedValue([{ ...plans[1], annual_price_cents: 15300 }]);
  mount();
  await screen.findByRole("article", { name: "Pro plan" });
  fireEvent.click(screen.getByRole("radio", { name: "Annual" }));
  expect(screen.getByText(`Save ${formatMoney(5100)} per year (25%)`)).toBeInTheDocument();
});
it("sends signed-out visitors to registration", async () => {
  mount();
  for (const plan of plans)
    expect(await screen.findByRole("link", { name: `Start free — ${plan.name}` })).toHaveAttribute(
      "href",
      ROUTES.auth.register,
    );
});
it("sends signed-in users to the billing page", async () => {
  auth.user = { id: "u1" };
  mount();
  for (const plan of plans)
    expect(await screen.findByRole("link", { name: `Choose plan — ${plan.name}` })).toHaveAttribute(
      "href",
      ROUTES.billing,
    );
});
