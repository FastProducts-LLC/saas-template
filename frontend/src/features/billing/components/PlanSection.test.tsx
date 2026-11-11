import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as endpoints from "../api/endpoints";
import { ApiError } from "../../../shared/api";
import { track } from "../../../shared/lib/track";
import { EVENTS } from "../../../shared/lib/events";
import type { PlanSubscription, PlanSpec } from "../model/types";
import PlanSection from "./PlanSection";

vi.mock("../api/endpoints");
vi.mock("../../../shared/lib/track", () => ({ track: vi.fn() }));
const mocked = vi.mocked(endpoints);
const plans: PlanSpec[] = [
  {
    plan: "free",
    name: "Free",
    monthly_price_cents: 0,
    annual_price_cents: 0,
    monthly_credits: 10,
    purchasable: { monthly: false, annual: false },
  },
  {
    plan: "pro",
    name: "Pro",
    monthly_price_cents: 1500,
    annual_price_cents: 15000,
    monthly_credits: 100,
    purchasable: { monthly: true, annual: true },
  },
  {
    plan: "team",
    name: "Team",
    monthly_price_cents: 4500,
    annual_price_cents: 45000,
    monthly_credits: 500,
    purchasable: { monthly: true, annual: false },
  },
];
const subscription: PlanSubscription = {
  plan: "pro",
  interval: "monthly",
  status: "active",
  current_period_end: "2026-12-15T12:00:00Z",
  cancel_at_period_end: false,
};
const date = new Date(subscription.current_period_end!).toLocaleDateString();
function mount(admin = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <PlanSection orgId="o1" admin={admin} />
    </QueryClientProvider>,
  );
  return client;
}
function subscribed(overrides: Partial<PlanSubscription> = {}) {
  mocked.getBillingPlan.mockResolvedValue({
    plan: "pro",
    subscription: { ...subscription, ...overrides },
  });
}
beforeEach(() => {
  vi.clearAllMocks();
  mocked.listPlans.mockResolvedValue(plans);
  mocked.getBillingPlan.mockResolvedValue({ plan: "free", subscription: null });
  mocked.createPlanCheckout.mockResolvedValue({ url: "https://stripe.test/checkout" });
  mocked.createPortal.mockResolvedValue({ url: "https://stripe.test/portal" });
  Object.defineProperty(window, "location", {
    configurable: true,
    writable: true,
    value: { href: "" },
  });
});
afterEach(cleanup);

it("shows the Free plan when there is no subscription", async () => {
  mount();
  expect(await screen.findByTestId("plan-current-name")).toHaveTextContent("Free");
  expect(screen.getByRole("article", { name: "Free plan" })).toBeInTheDocument();
});
it("shows plan, interval and renewal date for an active subscription", async () => {
  subscribed();
  mount();
  expect(await screen.findByTestId("plan-current-name")).toHaveTextContent("Pro");
  expect(screen.getByText("Billing").nextSibling).toHaveTextContent("Monthly");
  expect(screen.getByText("active")).toBeInTheDocument();
  expect(screen.getByText("Renewal date").nextSibling).toHaveTextContent(date);
  expect(screen.queryByRole("button", { name: /Subscribe/ })).not.toBeInTheDocument();
});
it("shows a cancellation notice when the plan is set to end", async () => {
  subscribed({ cancel_at_period_end: true });
  mount();
  expect(await screen.findByRole("alert")).toHaveTextContent(`Your plan ends on ${date}.`);
});
it("shows a past-due warning with a link to update payment", async () => {
  subscribed({ status: "past_due" });
  mount();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Payment failed. Access continues for a limited time.",
  );
  fireEvent.click(screen.getByRole("button", { name: "Update payment method" }));
  await waitFor(() => expect(window.location.href).toBe("https://stripe.test/portal"));
});
it("shows the trial end date while trialing", async () => {
  subscribed({ status: "trialing" });
  mount();
  expect((await screen.findByText("Trial ends")).nextSibling).toHaveTextContent(date);
});
it("starts checkout for the selected plan and interval", async () => {
  const client = mount();
  fireEvent.click(await screen.findByRole("radio", { name: "Annual" }));
  fireEvent.click(screen.getByRole("button", { name: "Subscribe to Pro" }));
  await waitFor(() =>
    expect(mocked.createPlanCheckout).toHaveBeenCalledWith("o1", {
      plan: "pro",
      interval: "annual",
    }),
  );
  await waitFor(() => expect(window.location.href).toBe("https://stripe.test/checkout"));
  expect(client.getQueryState(["orgs", "o1", "billing-plan"])).toBeDefined();
  expect(mocked.getBillingPlan.mock.calls.length).toBeGreaterThan(1);
});
it("tracks plan_checkout_started once on successful checkout", async () => {
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Subscribe to Pro" }));
  await waitFor(() =>
    expect(track).toHaveBeenCalledExactlyOnceWith(EVENTS.plan_checkout_started, {
      plan: "pro",
      interval: "monthly",
    }),
  );
});
it("disables subscribing to a plan that is not purchasable", async () => {
  mount();
  fireEvent.click(await screen.findByRole("radio", { name: "Annual" }));
  const button = screen.getByRole("button", { name: "Subscribe to Team" });
  expect(button).toBeDisabled();
  fireEvent.click(button);
  expect(mocked.createPlanCheckout).not.toHaveBeenCalled();
  expect(screen.getByText("This billing interval is currently unavailable.")).toBeInTheDocument();
});
it("opens the billing portal from Manage plan", async () => {
  subscribed();
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Manage plan" }));
  await waitFor(() => expect(mocked.createPortal).toHaveBeenCalledWith("o1"));
  await waitFor(() => expect(window.location.href).toBe("https://stripe.test/portal"));
});
it("hides subscribe and manage controls from members who cannot manage billing", async () => {
  mount(false);
  expect(await screen.findByTestId("plan-current-name")).toHaveTextContent("Free");
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  cleanup();
  subscribed({ status: "past_due" });
  mount(false);
  await waitFor(() => expect(screen.getByTestId("plan-current-name")).toHaveTextContent("Pro"));
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

it("offers Manage plan when checkout reports an existing subscription", async () => {
  mocked.createPlanCheckout.mockRejectedValue(
    new ApiError(409, "ERR_BILL_009", "Subscription already active"),
  );
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Subscribe to Pro" }));
  fireEvent.click(await screen.findByRole("button", { name: "Manage plan" }));
  await waitFor(() => expect(window.location.href).toBe("https://stripe.test/portal"));
  expect(screen.queryByRole("button", { name: /Subscribe/ })).not.toBeInTheDocument();
  expect(track).not.toHaveBeenCalledWith(EVENTS.plan_checkout_started, expect.anything());
});
