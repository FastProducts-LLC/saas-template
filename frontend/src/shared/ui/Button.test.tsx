import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import Button from "./Button";

// The project's vitest config doesn't enable `globals`, so Testing Library's
// automatic per-test cleanup isn't registered — do it explicitly here.
afterEach(cleanup);

describe("Button", () => {
  it("renders the primary variant by default", () => {
    render(<Button>Save</Button>);
    const btn = screen.getByRole("button", { name: "Save" });
    expect(btn).toBeInTheDocument();
    expect(btn.className).toContain("bg-[var(--ink)]");
  });

  it("renders the secondary variant", () => {
    render(<Button variant="secondary">Cancel</Button>);
    const btn = screen.getByRole("button", { name: "Cancel" });
    expect(btn.className).toContain("border-[var(--line)]");
  });

  it("renders the danger variant text-first (no fill)", () => {
    render(<Button variant="danger">Delete</Button>);
    const btn = screen.getByRole("button", { name: "Delete" });
    expect(btn.className).toContain("text-[var(--danger)]");
    expect(btn.className).not.toContain("bg-[var(--danger)]");
  });

  it("renders the danger-confirm variant filled, for final confirmations", () => {
    render(<Button variant="danger-confirm">Delete Key</Button>);
    const btn = screen.getByRole("button", { name: "Delete Key" });
    expect(btn.className).toContain("bg-[var(--danger)]");
    expect(btn.className).toContain("text-white");
  });

  it("disables and shows a spinner while loading", () => {
    const { container } = render(<Button loading>Submitting</Button>);
    const btn = screen.getByRole("button", { name: "Submitting" });
    expect(btn).toBeDisabled();
    expect(container.querySelector("svg.animate-spin")).toBeInTheDocument();
  });

  it("merges a custom className", () => {
    render(<Button className="w-full">Wide</Button>);
    expect(screen.getByRole("button", { name: "Wide" }).className).toContain("w-full");
  });
});
