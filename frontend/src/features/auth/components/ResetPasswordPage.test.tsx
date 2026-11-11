import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../../shared/api";
import ResetPasswordPage from "./ResetPasswordPage";

vi.mock("../api/endpoints");

import { resetPassword } from "../api/endpoints";

afterEach(cleanup);
beforeEach(() => vi.clearAllMocks());

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ResetPasswordPage />
    </MemoryRouter>,
  );
}

describe("ResetPasswordPage", () => {
  it("submits the new password using the token from the URL", async () => {
    vi.mocked(resetPassword).mockResolvedValue(undefined);
    renderAt("/reset-password?token=abc123&next=/settings");

    fireEvent.change(screen.getByPlaceholderText("New password"), {
      target: { value: "zephyr92mango" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
      target: { value: "zephyr92mango" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Set new password" }));

    await screen.findByText(/your password has been updated/i);
    expect(resetPassword).toHaveBeenCalledWith("abc123", "zephyr92mango", "zephyr92mango");
    expect(screen.getByTestId("reset-password-login-link")).toHaveAttribute(
      "href",
      "/login?next=%2Fsettings",
    );
  });

  it("can reveal and hide both password fields", () => {
    renderAt("/reset-password?token=abc123");
    const passwordInput = screen.getByTestId("reset-password-password-input");
    const confirmationInput = screen.getByTestId("reset-password-confirm-password-input");

    expect(passwordInput).toHaveAttribute("type", "password");
    fireEvent.click(screen.getByRole("button", { name: "Show new password" }));
    expect(passwordInput).toHaveAttribute("type", "text");
    fireEvent.click(screen.getByRole("button", { name: "Hide new password" }));
    expect(passwordInput).toHaveAttribute("type", "password");

    expect(confirmationInput).toHaveAttribute("type", "password");
    fireEvent.click(screen.getByRole("button", { name: "Show password confirmation" }));
    expect(confirmationInput).toHaveAttribute("type", "text");
    fireEvent.click(screen.getByRole("button", { name: "Hide password confirmation" }));
    expect(confirmationInput).toHaveAttribute("type", "password");
  });

  it("shows password requirements and blocks weak passwords", () => {
    renderAt("/reset-password?token=abc123");

    fireEvent.change(screen.getByPlaceholderText("New password"), {
      target: { value: "short" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
      target: { value: "short" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Set new password" }));

    expect(screen.getByTestId("password-rules")).toBeInTheDocument();
    expect(screen.getByText("Password does not meet the requirements below.")).toBeInTheDocument();
    expect(resetPassword).not.toHaveBeenCalled();
  });

  it("shows the missing-token state when no token is present", () => {
    renderAt("/reset-password");
    expect(screen.getByText(/missing its token/i)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("New password")).not.toBeInTheDocument();
  });

  it("shows a mismatch error and does not call the endpoint", () => {
    renderAt("/reset-password?token=abc123");

    fireEvent.change(screen.getByPlaceholderText("New password"), {
      target: { value: "zephyr92mango" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
      target: { value: "different99" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Set new password" }));

    expect(screen.getByText("The two passwords you entered don't match.")).toBeInTheDocument();
    expect(resetPassword).not.toHaveBeenCalled();
  });

  it("surfaces an invalid/expired token error from the endpoint", async () => {
    vi.mocked(resetPassword).mockRejectedValue(
      new ApiError(400, "ERR_AUTH_004", "This reset link has expired."),
    );
    renderAt("/reset-password?token=stale");

    fireEvent.change(screen.getByPlaceholderText("New password"), {
      target: { value: "zephyr92mango" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm new password"), {
      target: { value: "zephyr92mango" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Set new password" }));

    expect(
      await screen.findByText(
        "This link is no longer valid — it may have expired or already been used.",
      ),
    ).toBeInTheDocument();
  });
});
