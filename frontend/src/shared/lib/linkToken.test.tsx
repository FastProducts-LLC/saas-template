import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { readLinkToken, useLinkToken } from "./linkToken";

afterEach(cleanup);

function Probe() {
  const token = useLinkToken();
  const location = useLocation();
  return (
    <>
      <span data-testid="token">{token}</span>
      <span data-testid="url">{`${location.pathname}${location.search}${location.hash}`}</span>
    </>
  );
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Probe />
    </MemoryRouter>,
  );
}

describe("readLinkToken", () => {
  it("prefers the fragment, falls back to the query string", () => {
    expect(readLinkToken("#token=frag", "?token=query")).toBe("frag");
    expect(readLinkToken("", "?token=query")).toBe("query");
    expect(readLinkToken("", "")).toBe("");
  });
});

describe("useLinkToken", () => {
  it("reads a fragment token and scrubs it from the URL", async () => {
    renderAt("/reset-password?next=/settings#token=abc123");
    expect(screen.getByTestId("token")).toHaveTextContent("abc123");
    // Other params survive (URLSearchParams re-encodes the slash).
    expect(await screen.findByText("/reset-password?next=%2Fsettings")).toBeInTheDocument();
    // The captured token survives the scrub.
    expect(screen.getByTestId("token")).toHaveTextContent("abc123");
  });

  it("still accepts and scrubs a legacy ?token= link", async () => {
    renderAt("/verify-email?token=old456");
    expect(screen.getByTestId("token")).toHaveTextContent("old456");
    expect(await screen.findByText("/verify-email")).toBeInTheDocument();
  });

  it("returns an empty token when the link has none", () => {
    renderAt("/verify-email");
    expect(screen.getByTestId("token")).toHaveTextContent("");
  });
});
