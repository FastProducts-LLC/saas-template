import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import SaasFeaturesPage from "./SaasFeaturesPage";

function featureRowIds() {
  return screen.getAllByTestId("saas-feature-row").map((row) => row.getAttribute("data-id"));
}

function renderPage() {
  return render(
    <MemoryRouter>
      <SaasFeaturesPage />
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
});

describe("SaasFeaturesPage", () => {
  it("renders the full SaaS feature catalog", () => {
    renderPage();

    expect(screen.getByText("SaaS Essentials")).toBeInTheDocument();
    expect(screen.getAllByTestId("saas-build-phase")).toHaveLength(4);
    expect(screen.getAllByTestId("saas-feature-row")).toHaveLength(28);
    expect(featureRowIds()).toContain("auth");
    expect(featureRowIds()).toContain("enterprise-security");
    expect(featureRowIds()).toContain("subscription-billing");
  });

  it("filters by blueprint status", () => {
    renderPage();

    fireEvent.change(screen.getByTestId("saas-features-status-filter"), {
      target: { value: "blueprint" },
    });

    expect(screen.getAllByTestId("saas-feature-row")).toHaveLength(17);
    expect(featureRowIds()).toContain("notifications");
    expect(featureRowIds()).toContain("object-storage");
    expect(featureRowIds()).not.toContain("auth");
  });

  it("searches feature titles and implementation notes", () => {
    renderPage();

    fireEvent.change(screen.getByTestId("saas-features-search"), {
      target: { value: "delivery worker" },
    });

    expect(screen.getAllByTestId("saas-feature-row")).toHaveLength(1);
    expect(featureRowIds()).toEqual(["webhooks"]);
  });

  it("expands implementation details for a feature", () => {
    renderPage();

    fireEvent.click(screen.getAllByTestId("saas-feature-detail-toggle")[0]);

    expect(screen.getByTestId("saas-feature-detail")).toHaveAttribute("data-id", "auth");
    expect(screen.getByText("refresh_tokens")).toBeInTheDocument();
    expect(
      screen.getByText(/route-level rate limits protect high-risk auth endpoints/),
    ).toBeInTheDocument();
  });
});
