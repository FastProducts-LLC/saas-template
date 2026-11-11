import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import UsageSection from "./UsageSection";
import type { CreditUsage, UsageActor } from "../../credits";

const useCreditUsage = vi.fn();
const setLimitMutate = vi.fn();
const clearLimitMutate = vi.fn();

vi.mock("../../credits", () => ({
  useCreditUsage: (orgId: string | undefined, period: string) => useCreditUsage(orgId, period),
  useSetMemberLimit: () => ({ mutate: setLimitMutate }),
  useClearMemberLimit: () => ({ mutate: clearLimitMutate }),
}));

function actor(overrides: Partial<UsageActor>): UsageActor {
  return {
    user_id: null,
    user_email: null,
    user_name: null,
    api_key_id: null,
    api_key_name: null,
    credits: 0,
    count: 0,
    limit: null,
    actions: [],
    ...overrides,
  };
}

const usage: CreditUsage = {
  period: "2026-07",
  total_actors: 4,
  total_credits: 21,
  items: [
    actor({
      user_id: "u1",
      user_email: "alice@example.com",
      user_name: "Alice Smith",
      credits: 12,
      count: 8,
      limit: 50,
      actions: [
        { action: "llm_call", count: 6, credits: 6 },
        { action: "image_nano_banana", count: 2, credits: 4 },
      ],
    }),
    actor({
      api_key_id: "k1",
      api_key_name: "Zapier integration",
      credits: 6,
      count: 6,
      actions: [{ action: "llm_call", count: 6, credits: 6 }],
    }),
    actor({
      credits: 2,
      count: 1,
      actions: [{ action: "image_nano_banana", count: 1, credits: 2 }],
    }),
    actor({
      user_id: "u2",
      user_email: "bob@example.com",
      credits: 1,
      count: 1,
      actions: [{ action: "llm_call", count: 1, credits: 1 }],
    }),
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  useCreditUsage.mockReturnValue({ data: usage, isPending: false });
});

afterEach(cleanup);

describe("UsageSection", () => {
  it("renders member, api-key, and removed-member rows with breakdowns", () => {
    render(<UsageSection orgId="o1" admin={false} />);

    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    expect(screen.getByText("Alice Smith")).toBeInTheDocument();
    expect(screen.getByText("6 LLM calls · 2 images")).toBeInTheDocument();
    expect(screen.getByText("Zapier integration")).toBeInTheDocument();
    expect(screen.getByText("API key")).toBeInTheDocument();
    expect(screen.getByText("Removed member")).toBeInTheDocument();
    expect(screen.getByText("21 spent")).toBeInTheDocument();
  });

  it("shows limit progress for members with a cap", () => {
    render(<UsageSection orgId="o1" admin={false} />);
    expect(screen.getByText("12 / 50")).toBeInTheDocument();
  });

  it("lets admins set a limit for an uncapped member", () => {
    render(<UsageSection orgId="o1" admin={true} />);

    fireEvent.click(screen.getAllByText("Set limit")[0]);
    const input = screen.getByLabelText("Monthly credit limit");
    fireEvent.change(input, { target: { value: "30" } });
    fireEvent.click(screen.getByText("Save"));

    expect(setLimitMutate).toHaveBeenCalledWith({ userId: "u2", monthlyLimit: 30 });
  });

  it("refetches when the period changes", () => {
    render(<UsageSection orgId="o1" admin={false} />);

    const select = screen.getByLabelText("Usage period");
    const previous = (select as HTMLSelectElement).options[1].value;
    fireEvent.change(select, { target: { value: previous } });

    expect(useCreditUsage).toHaveBeenLastCalledWith("o1", previous);
  });

  it("renders an empty state when the period has no usage", () => {
    useCreditUsage.mockReturnValue({
      data: { period: "2026-07", items: [], total_actors: 0, total_credits: 0 },
      isPending: false,
    });
    render(<UsageSection orgId="o1" admin={false} />);
    expect(screen.getByText(/No usage in/)).toBeInTheDocument();
  });
});
