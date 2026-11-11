import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import LegalPage from "./LegalPage";
import PrivacyPage from "./PrivacyPage";
import TermsPage from "./TermsPage";

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("LegalPage markdown renderer", () => {
  const sample = [
    "<!-- config comment must not render -->",
    "# Title",
    "",
    "## Section One",
    "",
    "A paragraph with **bold text** and a [link](/privacy).",
    "",
    "- first item",
    "- second item with **emphasis**",
  ].join("\n");

  it("renders headings, paragraphs, bold, links, and lists", () => {
    renderWithRouter(<LegalPage markdown={sample} />);

    expect(screen.getByRole("heading", { level: 1, name: "Title" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Section One" })).toBeInTheDocument();
    expect(screen.getByText("bold text").tagName).toBe("STRONG");
    expect(screen.getByRole("link", { name: "link" })).toHaveAttribute("href", "/privacy");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("never renders the HTML comment config block", () => {
    renderWithRouter(<LegalPage markdown={sample} />);
    expect(screen.queryByText(/config comment/)).not.toBeInTheDocument();
  });
});

describe("legal documents", () => {
  it("renders the Terms of Service", () => {
    renderWithRouter(<TermsPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Terms of Service" })).toBeInTheDocument();
    // The arbitration opt-out is a load-bearing clause — fail loudly if dropped.
    expect(screen.getByText(/30-day opt-out/)).toBeInTheDocument();
  });

  it("renders the Privacy Policy", () => {
    renderWithRouter(<PrivacyPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Privacy Policy" })).toBeInTheDocument();
    // The no-sale commitment is load-bearing copy — fail loudly if dropped.
    expect(screen.getAllByText(/We do not sell Personal Information/).length).toBeGreaterThan(0);
  });
});
