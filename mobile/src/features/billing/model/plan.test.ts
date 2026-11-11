import { describe, expect, it } from "vitest";
import { describePlan } from "./plan";
import type { BillingPlan } from "./types";

const paid = (overrides: Partial<NonNullable<BillingPlan["subscription"]>> = {}): BillingPlan => ({
  plan: "pro",
  subscription: {
    plan: "pro", interval: "monthly", status: "active",
    current_period_end: "2026-12-15T00:00:00Z", cancel_at_period_end: false,
    ...overrides,
  },
});

describe("describePlan", () => {
  it("describes the free plan", () => {
    expect(describePlan({ plan: "free", subscription: null })).toEqual({
      title: "Free plan", subtitle: "No recurring subscription", tone: "neutral",
    });
  });
  it("describes an active paid plan with its renewal date", () => {
    expect(describePlan(paid())).toEqual({
      title: "Pro plan", subtitle: "Monthly · active · Renews Dec 15, 2026", tone: "neutral",
    });
    expect(describePlan(paid({ interval: "annual" })).subtitle).toContain("Annual");
  });
  it("describes a plan that ends at period end", () => {
    const result = describePlan(paid({ cancel_at_period_end: true }));
    expect(result.subtitle).toBe("Monthly · active · Ends Dec 15, 2026");
    expect(result.tone).toBe("neutral");
  });
  it("describes a past-due plan as a warning", () => {
    const result = describePlan(paid({ status: "past_due" }));
    expect(result.tone).toBe("warning");
    expect(result.subtitle).toContain("Payment is past due.");
    expect(result.subtitle).toContain("Period ends Dec 15, 2026");
  });
  it("describes a trial with its end date", () => {
    const result = describePlan(paid({ status: "trialing" }));
    expect(result.subtitle).toBe("Monthly · trialing · Trial ends Dec 15, 2026");
    expect(result.tone).toBe("neutral");
  });
});
