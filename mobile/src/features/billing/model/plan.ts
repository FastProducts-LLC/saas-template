import type { BillingPlan } from "./types";

export function describePlan(billing: BillingPlan): {
  title: string;
  subtitle: string;
  tone: "neutral" | "warning";
} {
  const title = `${billing.plan.charAt(0).toUpperCase()}${billing.plan.slice(1)} plan`;
  const subscription = billing.subscription;
  if (!subscription) return { title, subtitle: "No recurring subscription", tone: "neutral" };

  const parts = [
    subscription.interval === "monthly" ? "Monthly" : "Annual",
    subscription.status.replace(/_/g, " "),
  ];
  if (subscription.current_period_end) {
    const date = new Date(subscription.current_period_end).toLocaleDateString("en-US", {
      year: "numeric", month: "short", day: "numeric", timeZone: "UTC",
    });
    const label = subscription.cancel_at_period_end || subscription.status === "canceled"
      ? "Ends"
      : subscription.status === "trialing"
        ? "Trial ends"
        : subscription.status === "active" ? "Renews" : "Period ends";
    parts.push(`${label} ${date}`);
  }
  if (subscription.status === "past_due") parts.push("Payment is past due.");
  return {
    title,
    subtitle: parts.join(" · "),
    tone: subscription.status === "past_due" ? "warning" : "neutral",
  };
}
