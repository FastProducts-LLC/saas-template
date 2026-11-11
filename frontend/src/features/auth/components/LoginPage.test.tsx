import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../../shared/api";
import LoginPage from "./LoginPage";

// LoginPage gets login() from the auth context (useAuth) — mock that boundary
// rather than the endpoint module.
const login = vi.fn();
vi.mock("../model/session", () => ({
  useAuth: () => ({ login }),
}));

afterEach(cleanup);
beforeEach(() => vi.clearAllMocks());

function renderAt(path = "/login") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={<div>Dashboard screen</div>} />
        <Route path="/billing" element={<div>Billing screen</div>} />
        <Route path="/settings" element={<div>Settings screen</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LoginPage", () => {
  it("renders email and password fields", () => {
    renderAt();
    expect(
      screen.getByText("Use your account credentials to continue to Dashboard."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Email")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("can reveal and hide the password", () => {
    renderAt();
    const passwordInput = screen.getByTestId("login-password-input");

    expect(passwordInput).toHaveAttribute("type", "password");
    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(passwordInput).toHaveAttribute("type", "text");
    fireEvent.click(screen.getByRole("button", { name: "Hide password" }));
    expect(passwordInput).toHaveAttribute("type", "password");
  });

  it("calls login with the entered credentials on submit", async () => {
    login.mockResolvedValue(undefined);
    renderAt();

    fireEvent.change(screen.getByPlaceholderText("Email"), {
      target: { value: "ada@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Password"), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(login).toHaveBeenCalledWith("ada@example.com", "secret123"));
  });

  it("navigates to /dashboard by default on success", async () => {
    login.mockResolvedValue(undefined);
    renderAt();

    fireEvent.change(screen.getByPlaceholderText("Email"), {
      target: { value: "ada@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Password"), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Dashboard screen")).toBeInTheDocument();
  });

  it("respects the ?next= redirect param on success", async () => {
    login.mockResolvedValue(undefined);
    renderAt("/login?next=/billing");

    fireEvent.change(screen.getByPlaceholderText("Email"), {
      target: { value: "ada@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Password"), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Billing screen")).toBeInTheDocument();
  });

  it("preserves a safe next destination on recovery and registration links", () => {
    renderAt("/login?next=/settings");

    expect(screen.getByTestId("login-forgot-link")).toHaveAttribute(
      "href",
      "/forgot-password?next=%2Fsettings",
    );
    expect(screen.getByTestId("login-register-link")).toHaveAttribute(
      "href",
      "/register?next=%2Fsettings",
    );
  });

  it("falls back to the dashboard when the next destination is unsafe", async () => {
    login.mockResolvedValue(undefined);
    renderAt("/login?next=https://evil.example/account");

    fireEvent.change(screen.getByPlaceholderText("Email"), {
      target: { value: "ada@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Password"), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Dashboard screen")).toBeInTheDocument();
  });

  it("renders the error message when login rejects", async () => {
    login.mockRejectedValue(new ApiError(401, "ERR_AUTH_001", "Invalid email or password."));
    renderAt();

    fireEvent.change(screen.getByPlaceholderText("Email"), {
      target: { value: "ada@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Password"), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    // Catalog copy, not the server's developer-facing detail.
    expect(
      await screen.findByText("That email and password combination didn't match our records."),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("We could not sign you in.");
    expect(screen.getByRole("link", { name: "Reset password" })).toBeInTheDocument();
  });
});
