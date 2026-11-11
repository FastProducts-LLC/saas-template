import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RegisterPage from "./RegisterPage";

// RegisterPage gets register() from the auth context (useAuth).
const register = vi.fn();
vi.mock("../model/session", () => ({
  useAuth: () => ({ register }),
}));

afterEach(cleanup);
beforeEach(() => vi.clearAllMocks());

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/register"]}>
      <Routes>
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/dashboard" element={<div>Dashboard screen</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function fillValidForm() {
  fireEvent.change(screen.getByPlaceholderText("First name"), { target: { value: "Ada" } });
  fireEvent.change(screen.getByPlaceholderText("Last name"), { target: { value: "Lovelace" } });
  fireEvent.change(screen.getByPlaceholderText("Email"), {
    target: { value: "ada@example.com" },
  });
  fireEvent.change(screen.getByPlaceholderText("Password"), {
    target: { value: "zephyr92mango" },
  });
  fireEvent.change(screen.getByPlaceholderText("Confirm password"), {
    target: { value: "zephyr92mango" },
  });
}

function acceptTerms() {
  // First checkbox = terms, second = marketing.
  fireEvent.click(screen.getAllByRole("checkbox")[0]);
}

describe("RegisterPage", () => {
  it("renders all account fields", () => {
    renderPage();
    expect(screen.getByPlaceholderText("First name")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Last name")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Email")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Password")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Confirm password")).toBeInTheDocument();
    expect(screen.getAllByRole("checkbox")).toHaveLength(2);
  });

  it("shows password rule feedback that reacts to typing", () => {
    renderPage();
    // No rules visible until the user types in the password field.
    expect(screen.queryByText("At least 12 characters")).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Password"), { target: { value: "abc" } });
    expect(screen.getByText("At least 12 characters")).toBeInTheDocument();
    expect(screen.getByText("Mix of letters and numbers")).toBeInTheDocument();
    expect(screen.getByText("Not a commonly used password")).toBeInTheDocument();
  });

  it("shows a mismatch message when the confirmation differs", () => {
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Password"), {
      target: { value: "zephyr92mango" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm password"), {
      target: { value: "different" },
    });
    expect(screen.getByText("Passwords do not match.")).toBeInTheDocument();
  });

  it("disables the submit button until the terms are accepted", () => {
    renderPage();
    const submit = screen.getByRole("button", { name: "Create Account" });
    expect(submit).toBeDisabled();

    acceptTerms();
    expect(submit).toBeEnabled();
  });

  it("does not call register when required fields are blank, even with consent given", () => {
    renderPage();
    // Valid password/confirmation and the terms box checked, but
    // first name and email are left blank — the submit button's disabled
    // condition no longer checks these itself; only the form's native
    // `required` inputs should block the submit event from firing.
    fireEvent.change(screen.getByPlaceholderText("Password"), {
      target: { value: "zephyr92mango" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirm password"), {
      target: { value: "zephyr92mango" },
    });
    acceptTerms();

    fireEvent.click(screen.getByRole("button", { name: "Create Account" }));

    expect(register).not.toHaveBeenCalled();
  });

  it("calls register and navigates to /dashboard on success", async () => {
    register.mockResolvedValue(undefined);
    renderPage();

    fillValidForm();
    acceptTerms();
    fireEvent.click(screen.getByRole("button", { name: "Create Account" }));

    await waitFor(() =>
      expect(register).toHaveBeenCalledWith(
        expect.objectContaining({
          first_name: "Ada",
          last_name: "Lovelace",
          email: "ada@example.com",
          password: "zephyr92mango",
          password_confirmation: "zephyr92mango",
          terms_accepted: true,
          marketing_opt_in: false,
        }),
      ),
    );
    expect(await screen.findByText("Dashboard screen")).toBeInTheDocument();
  });

  it("shows 'check your email' instead of navigating under verify-first signup", async () => {
    register.mockResolvedValue(true);
    renderPage();

    fillValidForm();
    acceptTerms();
    fireEvent.click(screen.getByRole("button", { name: "Create Account" }));

    expect(await screen.findByTestId("register-check-email")).toHaveTextContent("ada@example.com");
    expect(screen.queryByText("Dashboard screen")).not.toBeInTheDocument();
  });

  it("blocks submit and warns when the password is too weak", async () => {
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("First name"), { target: { value: "Ada" } });
    fireEvent.change(screen.getByPlaceholderText("Email"), {
      target: { value: "ada@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Password"), { target: { value: "weak" } });
    fireEvent.change(screen.getByPlaceholderText("Confirm password"), {
      target: { value: "weak" },
    });
    acceptTerms();
    fireEvent.click(screen.getByRole("button", { name: "Create Account" }));

    expect(
      await screen.findByText("Password does not meet the requirements below."),
    ).toBeInTheDocument();
    expect(register).not.toHaveBeenCalled();
  });
});
