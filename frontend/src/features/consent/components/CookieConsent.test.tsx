import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CONSENT_VERSION, openCookieSettings, storeConsent } from "../model/store";
import CookieConsent from "./CookieConsent";

let fakeUser: { id: string } | null = null;
vi.mock("../../auth", () => ({
  useAuth: () => ({ user: fakeUser }),
}));

vi.mock("../../../shared/lib/track", () => ({
  loadAnalytics: vi.fn(),
  grantAnalyticsConsent: vi.fn(),
  denyAnalyticsConsent: vi.fn(),
}));

vi.mock("../api/endpoints", () => ({
  fetchServerConsent: vi.fn().mockResolvedValue(null),
  recordServerConsent: vi.fn().mockResolvedValue({}),
}));

import {
  denyAnalyticsConsent,
  grantAnalyticsConsent,
  loadAnalytics,
} from "../../../shared/lib/track";
import { fetchServerConsent, recordServerConsent } from "../api/endpoints";

function renderBanner() {
  return render(
    <MemoryRouter>
      <CookieConsent />
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  localStorage.clear();
  fakeUser = null;
});
beforeEach(() => vi.clearAllMocks());

describe("CookieConsent", () => {
  it("shows the banner for an undecided visitor and hides after Accept all", async () => {
    renderBanner();
    expect(screen.getByTestId("cookie-banner")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Accept all" }));

    await waitFor(() => expect(screen.queryByTestId("cookie-banner")).not.toBeInTheDocument());
    expect(grantAnalyticsConsent).toHaveBeenCalled();
    expect(loadAnalytics).toHaveBeenCalled();
    expect(JSON.parse(localStorage.getItem("cookieConsent")!)).toMatchObject({
      version: CONSENT_VERSION,
      categories: { analytics: true },
    });
  });

  it("Reject all records the decision and never loads analytics", async () => {
    renderBanner();
    fireEvent.click(screen.getByRole("button", { name: "Reject all" }));

    await waitFor(() => expect(screen.queryByTestId("cookie-banner")).not.toBeInTheDocument());
    expect(denyAnalyticsConsent).toHaveBeenCalled();
    expect(loadAnalytics).not.toHaveBeenCalled();
    expect(JSON.parse(localStorage.getItem("cookieConsent")!)).toMatchObject({
      categories: { analytics: false },
    });
  });

  it("stays hidden for a returning visitor and enacts a stored grant", () => {
    storeConsent({ analytics: true });
    renderBanner();
    expect(screen.queryByTestId("cookie-banner")).not.toBeInTheDocument();
    expect(loadAnalytics).toHaveBeenCalled();
  });

  it("Customize saves a granular choice", async () => {
    renderBanner();
    fireEvent.click(screen.getByRole("button", { name: "Customize" }));

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();
    // Essential is on and locked; Analytics defaults off.
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes[0]).toBeChecked();
    expect(checkboxes[0]).toBeDisabled();
    expect(checkboxes[1]).not.toBeChecked();

    fireEvent.click(checkboxes[1]);
    fireEvent.click(screen.getByRole("button", { name: "Save preferences" }));

    await waitFor(() => expect(loadAnalytics).toHaveBeenCalled());
    expect(JSON.parse(localStorage.getItem("cookieConsent")!)).toMatchObject({
      categories: { analytics: true },
    });
  });

  it("re-opens preferences via openCookieSettings after a decision", async () => {
    storeConsent({ analytics: false });
    renderBanner();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    openCookieSettings();

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("syncs a signed-in user's decision to the backend audit trail", async () => {
    fakeUser = { id: "u1" };
    renderBanner();
    // Undecided + signed in: reconciles against the server first.
    await waitFor(() => expect(fetchServerConsent).toHaveBeenCalled());

    fireEvent.click(await screen.findByRole("button", { name: "Accept all" }));

    await waitFor(() =>
      expect(recordServerConsent).toHaveBeenCalledWith({ analytics: true }, CONSENT_VERSION),
    );
  });

  it("adopts a server-side decision from another device instead of re-prompting", async () => {
    fakeUser = { id: "u1" };
    vi.mocked(fetchServerConsent).mockResolvedValue({
      analytics: true,
      policy_version: CONSENT_VERSION,
      recorded_at: "2026-07-09T00:00:00Z",
    });
    renderBanner();

    await waitFor(() => expect(loadAnalytics).toHaveBeenCalled());
    expect(screen.queryByTestId("cookie-banner")).not.toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("cookieConsent")!)).toMatchObject({
      categories: { analytics: true },
    });
  });
});
