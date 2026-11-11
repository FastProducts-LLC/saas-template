import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { User } from "../model/types";
import ProfilePage from "./ProfilePage";

const fakeUser: User = {
  id: "u1",
  email: "ada@example.com",
  first_name: "Ada",
  last_name: "Lovelace",
  name: "Ada Lovelace",
  is_superuser: false,
  marketing_opt_in: false,
  analytics_opt_out: false,
  email_verified: false,
  created_at: "2024-01-01T00:00:00Z",
};

const refreshUser = vi.fn();
vi.mock("../model/session", () => ({
  useAuth: () => ({ user: fakeUser, refreshUser }),
}));

vi.mock("../api/endpoints");
vi.mock("../../../shared/lib/track", () => ({ track: vi.fn() }));

import {
  changePassword,
  resendVerification,
  updateAnalyticsOptOut,
  updateMarketingOptIn,
  updateProfile,
} from "../api/endpoints";
import { track } from "../../../shared/lib/track";

afterEach(cleanup);
beforeEach(() => vi.clearAllMocks());

describe("ProfilePage", () => {
  it("renders the user's name and email from the auth context", () => {
    render(<ProfilePage />);
    expect(screen.getByDisplayValue("Ada")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Lovelace")).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
    // The fake user is unverified, so the resend control is offered.
    expect(screen.getByText("Not verified")).toBeInTheDocument();
  });

  it("saves the name via updateProfile then refreshes the session", async () => {
    vi.mocked(updateProfile).mockResolvedValue(fakeUser);
    render(<ProfilePage />);

    fireEvent.change(screen.getByDisplayValue("Ada"), { target: { value: "Grace" } });
    fireEvent.click(screen.getByRole("button", { name: "Save name" }));

    await waitFor(() => expect(updateProfile).toHaveBeenCalledWith("Grace", "Lovelace"));
    expect(refreshUser).toHaveBeenCalledTimes(1);
    // The section only — never the name that was typed.
    expect(track).toHaveBeenCalledWith("settings_updated", { section: "profile_name" });
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("validates the change-password confirmation mismatch before calling the endpoint", () => {
    render(<ProfilePage />);

    fireEvent.change(screen.getByPlaceholderText("Current password"), {
      target: { value: "oldsecret1" },
    });
    fireEvent.change(screen.getByPlaceholderText("New password"), {
      target: { value: "zephyr92mango" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
      target: { value: "different99" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    expect(screen.getByText("Passwords do not match.")).toBeInTheDocument();
    expect(changePassword).not.toHaveBeenCalled();
  });

  it("blocks a weak new password in the change-password form", () => {
    render(<ProfilePage />);

    fireEvent.change(screen.getByPlaceholderText("Current password"), {
      target: { value: "oldsecret1" },
    });
    fireEvent.change(screen.getByPlaceholderText("New password"), {
      target: { value: "weak" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
      target: { value: "weak" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    expect(
      screen.getByText("New password does not meet the requirements below."),
    ).toBeInTheDocument();
    expect(changePassword).not.toHaveBeenCalled();
  });

  it("changes the password when the form is valid", async () => {
    vi.mocked(changePassword).mockResolvedValue(undefined);
    render(<ProfilePage />);

    fireEvent.change(screen.getByPlaceholderText("Current password"), {
      target: { value: "oldsecret1" },
    });
    fireEvent.change(screen.getByPlaceholderText("New password"), {
      target: { value: "zephyr92mango" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
      target: { value: "zephyr92mango" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    await waitFor(() =>
      expect(changePassword).toHaveBeenCalledWith("oldsecret1", "zephyr92mango", "zephyr92mango"),
    );
    expect(
      await screen.findByText("Password changed. Other devices have been signed out."),
    ).toBeInTheDocument();
  });

  it("resends the verification email for an unverified user", async () => {
    vi.mocked(resendVerification).mockResolvedValue(undefined);
    render(<ProfilePage />);

    fireEvent.click(screen.getByRole("button", { name: "Resend verification email" }));

    await waitFor(() => expect(resendVerification).toHaveBeenCalledTimes(1));
    expect(
      await screen.findByText("Verification email sent — check your inbox."),
    ).toBeInTheDocument();
  });

  it("updates the marketing opt-in toggle via the endpoint", async () => {
    vi.mocked(updateMarketingOptIn).mockResolvedValue(fakeUser);
    render(<ProfilePage />);

    // By test id: the page has a second checkbox (the analytics toggle).
    fireEvent.click(screen.getByTestId("profile-marketing-checkbox"));

    await waitFor(() => expect(updateMarketingOptIn).toHaveBeenCalledWith(true));
    expect(refreshUser).toHaveBeenCalled();
  });

  it("the analytics toggle is on by default and opts the account out when unchecked", async () => {
    vi.mocked(updateAnalyticsOptOut).mockResolvedValue({ ...fakeUser, analytics_opt_out: true });
    render(<ProfilePage />);

    const checkbox = screen.getByTestId("profile-analytics-checkbox") as HTMLInputElement;
    expect(checkbox.checked).toBe(true); // sharing = not opted out
    fireEvent.click(checkbox);

    await waitFor(() => expect(updateAnalyticsOptOut).toHaveBeenCalledWith(true));
    // refreshUser re-identifies, which is what applies the new setting.
    await waitFor(() => expect(refreshUser).toHaveBeenCalledTimes(1));
    // Opting out must not itself be reported to analytics.
    expect(track).not.toHaveBeenCalled();
  });

  it("surfaces a failed analytics toggle and does not refresh", async () => {
    vi.mocked(updateAnalyticsOptOut).mockRejectedValue(new Error("Could not save"));
    render(<ProfilePage />);

    fireEvent.click(screen.getByTestId("profile-analytics-checkbox"));

    expect(await screen.findByTestId("profile-analytics-error")).toBeInTheDocument();
    expect(refreshUser).not.toHaveBeenCalled();
  });
});
