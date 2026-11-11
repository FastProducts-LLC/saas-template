import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../../shared/api";
import ForgotPasswordPage from "./ForgotPasswordPage";

vi.mock("../api/endpoints");

import { forgotPassword } from "../api/endpoints";

afterEach(cleanup);
beforeEach(() => vi.clearAllMocks());

function renderPage(path = "/forgot-password") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ForgotPasswordPage />
    </MemoryRouter>,
  );
}

function submitEmail(email = "ada@example.com") {
  fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: email } });
  fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));
}

describe("ForgotPasswordPage", () => {
  it("renders the request form", () => {
    renderPage();
    expect(screen.getByText(/account recovery/i)).toBeInTheDocument();
    expect(screen.getByText(/continue to Dashboard/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Account email")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Email")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send reset link" })).toBeInTheDocument();
  });

  it("preserves the next destination on the sign-in link", () => {
    renderPage("/forgot-password?next=/billing");

    expect(screen.getByText(/continue to Billing/i)).toBeInTheDocument();
    expect(screen.getByTestId("forgot-password-login-link")).toHaveAttribute(
      "href",
      "/login?next=%2Fbilling",
    );
  });

  it("shows the neutral confirmation after a successful request", async () => {
    vi.mocked(forgotPassword).mockResolvedValue(undefined);
    renderPage();
    submitEmail();

    expect(await screen.findByText(/we have sent a/i)).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
    expect(forgotPassword).toHaveBeenCalledWith("ada@example.com");
    expect(screen.getByRole("alert")).toHaveTextContent("password reset link");
  });

  it("surfaces an error and withholds the confirmation when the request rejects", async () => {
    // No-enumeration is enforced server-side (the endpoint returns 200 for
    // unknown emails). When the call genuinely fails, the page shows the error
    // rather than the neutral confirmation. A code newer than this bundle's
    // catalog gets the vetted copy for its HTTP status — never server detail.
    vi.mocked(forgotPassword).mockRejectedValue(
      new ApiError(500, "ERR_ZZZ_999", "internal detail"),
    );
    renderPage();
    submitEmail("ghost@example.com");

    expect(
      await screen.findByText(
        "Something went wrong on our end. Your data is safe, and we've been notified.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("internal detail")).not.toBeInTheDocument();
    // The real code is kept for support even though the copy fell back.
    expect(screen.getByText(/ERR_ZZZ_999/)).toBeInTheDocument();
    expect(screen.queryByText(/we have sent a/i)).not.toBeInTheDocument();
  });
});
