import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../../shared/api";
import VerifyEmailPage from "./VerifyEmailPage";

vi.mock("../api/endpoints");

import { verifyEmail } from "../api/endpoints";

afterEach(cleanup);
beforeEach(() => vi.clearAllMocks());

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <VerifyEmailPage />
    </MemoryRouter>,
  );
}

describe("VerifyEmailPage", () => {
  it("auto-verifies with the token from the URL fragment (current email links)", async () => {
    vi.mocked(verifyEmail).mockResolvedValue(undefined);
    renderAt("/verify-email#token=frag123");

    expect(await screen.findByText(/your email address is verified/i)).toBeInTheDocument();
    expect(verifyEmail).toHaveBeenCalledTimes(1);
    expect(verifyEmail).toHaveBeenCalledWith("frag123");
  });

  it("auto-verifies on mount with the token from the URL and shows success", async () => {
    vi.mocked(verifyEmail).mockResolvedValue(undefined);
    renderAt("/verify-email?token=abc123");

    expect(await screen.findByText(/your email address is verified/i)).toBeInTheDocument();
    expect(verifyEmail).toHaveBeenCalledWith("abc123");
  });

  it("shows the error state when verification rejects", async () => {
    vi.mocked(verifyEmail).mockRejectedValue(
      new ApiError(400, "ERR_AUTH_004", "This verification link is invalid."),
    );
    renderAt("/verify-email?token=stale");

    expect(
      await screen.findByText(
        "This link is no longer valid — it may have expired or already been used.",
      ),
    ).toBeInTheDocument();
  });

  it("shows the missing-token error without calling the endpoint", () => {
    renderAt("/verify-email");
    expect(screen.getByText("This verification link is missing its token.")).toBeInTheDocument();
    expect(verifyEmail).not.toHaveBeenCalled();
  });
});
