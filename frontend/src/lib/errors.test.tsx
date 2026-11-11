import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useState, type ReactElement } from "react";

import { ApiError, claimError, getErrorMessage, publishError } from "../shared/api";
import { ErrorAlert } from "../shared/ui";
import { ErrorUIProvider, INLINE_CLAIM_GRACE_MS } from "./errors";

// vitest `globals` is off in this project, so Testing Library's automatic
// per-test cleanup isn't registered — do it (and timer/mock teardown) by hand.
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// The provider calls useQueryClient(), so every render needs a client in scope.
function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

// publishError only forwards real ApiError instances (instanceof + code/status),
// so the tests build genuine ApiError objects and let the catalog supply copy.
// Toasts wait INLINE_CLAIM_GRACE_MS for an inline claim; step past it.
function publish(err: ApiError, { claimInline = false } = {}) {
  act(() => {
    publishError(err);
    if (claimInline) claimError(err); // what a form's catch/onError does next
    vi.advanceTimersByTime(INLINE_CLAIM_GRACE_MS);
  });
}

describe("ErrorUIProvider", () => {
  beforeEach(() => {
    // Default to "online" so the offline banner doesn't bleed across tests
    // (the provider reads navigator.onLine in its initial state).
    vi.spyOn(navigator, "onLine", "get").mockReturnValue(true);
    vi.useFakeTimers();
  });

  it("renders its children", () => {
    renderWithClient(
      <ErrorUIProvider>
        <p>app content</p>
      </ErrorUIProvider>,
    );
    expect(screen.getByText("app content")).toBeInTheDocument();
  });

  it("shows a toast with the catalog userMessage for a toast-display error", () => {
    renderWithClient(
      <ErrorUIProvider>
        <p>app content</p>
      </ErrorUIProvider>,
    );

    // ERR_PERM_001 → display "toast", severity "info".
    publish(new ApiError(403, "ERR_PERM_001", "forbidden", "abc123"));

    const toast = screen.getByRole("alert");
    expect(
      within(toast).getByText("You don't have permission to do that in this organization."),
    ).toBeInTheDocument();
    // Reference combines code + correlation id for support.
    expect(within(toast).getByText("ERR_PERM_001 · abc123")).toBeInTheDocument();
  });

  it("auto-dismisses a toast after its severity TTL", () => {
    renderWithClient(
      <ErrorUIProvider>
        <p>app content</p>
      </ErrorUIProvider>,
    );

    // ERR_PERM_001 is severity "info" → 6_000ms TTL.
    publish(new ApiError(403, "ERR_PERM_001", "forbidden", "abc123"));
    expect(screen.getByRole("alert")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(6_000);
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("dismisses a toast when the dismiss button is clicked", () => {
    renderWithClient(
      <ErrorUIProvider>
        <p>app content</p>
      </ErrorUIProvider>,
    );

    publish(new ApiError(403, "ERR_PERM_001", "forbidden", "abc123"));
    const toast = screen.getByRole("alert");

    fireEvent.click(within(toast).getByLabelText("Dismiss"));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("dedupes a burst of the same code into a single toast", () => {
    renderWithClient(
      <ErrorUIProvider>
        <p>app content</p>
      </ErrorUIProvider>,
    );

    // Same code within the 2_500ms dedupe window → one toast only.
    publish(new ApiError(403, "ERR_PERM_001", "forbidden", "id-1"));
    publish(new ApiError(403, "ERR_PERM_001", "forbidden", "id-2"));

    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });

  it("shows distinct toasts for different codes", () => {
    renderWithClient(
      <ErrorUIProvider>
        <p>app content</p>
      </ErrorUIProvider>,
    );

    publish(new ApiError(403, "ERR_PERM_001", "forbidden", "id-1"));
    // ERR_CRD_001 → display "toast".
    publish(new ApiError(409, "ERR_CRD_001", "no credits", "id-2"));

    expect(screen.getAllByRole("alert")).toHaveLength(2);
  });

  it("renders the offline banner when a network error is published", () => {
    renderWithClient(
      <ErrorUIProvider>
        <p>app content</p>
      </ErrorUIProvider>,
    );

    // ERR_NET_001 is special-cased to the persistent offline banner, not a toast.
    publish(new ApiError(0, "ERR_NET_001", "Network error"));

    const banner = screen.getByRole("status");
    expect(banner).toHaveTextContent("We can't reach the internet right now.");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    // Children stay mounted under the banner.
    expect(screen.getByText("app content")).toBeInTheDocument();
  });

  it("renders the offline banner when the window fires an offline event", () => {
    renderWithClient(
      <ErrorUIProvider>
        <p>app content</p>
      </ErrorUIProvider>,
    );
    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    act(() => {
      window.dispatchEvent(new Event("offline"));
    });
    expect(screen.getByRole("status")).toHaveTextContent("We can't reach the internet right now.");
  });

  it("clears the offline banner when the window fires an online event", () => {
    renderWithClient(
      <ErrorUIProvider>
        <p>app content</p>
      </ErrorUIProvider>,
    );

    act(() => {
      window.dispatchEvent(new Event("offline"));
    });
    expect(screen.getByRole("status")).toBeInTheDocument();

    act(() => {
      window.dispatchEvent(new Event("online"));
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("takes over the screen with the maintenance page on a 503 maintenance error", () => {
    // MaintenancePage schedules a health-probe timer on mount; fake them so the
    // probe never fires real fetches during the assertion.
    renderWithClient(
      <ErrorUIProvider>
        <p>app content</p>
      </ErrorUIProvider>,
    );

    // ERR_SRV_003 → display "page"; special-cased to the maintenance takeover.
    publish(new ApiError(503, "ERR_SRV_003", "maintenance"));

    expect(
      screen.getByText("We're doing some quick maintenance and will be right back."),
    ).toBeInTheDocument();
    // The takeover replaces children entirely.
    expect(screen.queryByText("app content")).not.toBeInTheDocument();
    // No toast is shown for the maintenance page.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("skips the toast when a component shows the error inline", () => {
    renderWithClient(
      <ErrorUIProvider>
        <p>app content</p>
      </ErrorUIProvider>,
    );
    publish(new ApiError(409, "ERR_CRD_001", "no credits", "id-1"), { claimInline: true });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("treats getErrorMessage() as an inline claim", () => {
    renderWithClient(
      <ErrorUIProvider>
        <p>app content</p>
      </ErrorUIProvider>,
    );
    const err = new ApiError(409, "ERR_CRD_001", "no credits", "id-1");
    act(() => {
      publishError(err);
      getErrorMessage(err);
      vi.advanceTimersByTime(INLINE_CLAIM_GRACE_MS);
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("still shows the offline banner for a claimed network error", () => {
    renderWithClient(
      <ErrorUIProvider>
        <p>app content</p>
      </ErrorUIProvider>,
    );
    publish(new ApiError(0, "ERR_NET_001", "Network error"), { claimInline: true });
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("an <ErrorAlert> rendered for the error suppresses the toast", () => {
    let showInline: (err: ApiError) => void = () => {};
    function Form() {
      const [error, setError] = useState<ApiError | null>(null);
      showInline = setError;
      return <ErrorAlert error={error} />;
    }
    renderWithClient(
      <ErrorUIProvider>
        <Form />
      </ErrorUIProvider>,
    );
    const err = new ApiError(409, "ERR_CRD_001", "no credits", "id-9");
    act(() => {
      publishError(err); // api() publishes first…
    });
    act(() => {
      showInline(err); // …then the mutation's error state re-renders the form
    });
    act(() => {
      vi.advanceTimersByTime(INLINE_CLAIM_GRACE_MS);
    });
    expect(screen.getByTestId("error-alert")).toBeInTheDocument();
    expect(screen.queryByTestId("toast")).not.toBeInTheDocument();
  });

  it("control: the same error with no inline display does toast", () => {
    renderWithClient(
      <ErrorUIProvider>
        <p>app content</p>
      </ErrorUIProvider>,
    );
    publish(new ApiError(409, "ERR_CRD_001", "no credits", "id-9"));
    expect(screen.getByTestId("toast")).toBeInTheDocument();
  });
});

describe("<ErrorAlert>", () => {
  it("shows headline, one next step, field problems, and the support ref", () => {
    const err = new ApiError(422, "ERR_VAL_001", "Validation failed", "ref42", {
      display_name: "This field is required.",
      "members.0.email": "Enter a valid email address.",
      __root__: "The request couldn't be read.",
    });
    render(<ErrorAlert error={err} />);
    expect(screen.getByTestId("error-alert-message")).toHaveTextContent(
      "Some of the information looks incomplete or incorrect.",
    );
    const fields = screen.getByTestId("error-alert-fields");
    expect(fields).toHaveTextContent("Display name: This field is required.");
    expect(fields).toHaveTextContent("Email: Enter a valid email address.");
    expect(fields).toHaveTextContent("The request couldn't be read.");
    expect(screen.getByText("Check the highlighted fields and try again.")).toBeInTheDocument();
    expect(screen.getByTestId("error-alert-ref")).toHaveTextContent("ERR_VAL_001 · ref42");
  });

  it("omits fields the form already binds", () => {
    const err = new ApiError(422, "ERR_VAL_001", "x", null, { name: "Required." });
    render(<ErrorAlert error={err} hideFields />);
    expect(screen.queryByTestId("error-alert-fields")).not.toBeInTheDocument();
  });

  it("renders plain strings and nothing for empty values", () => {
    const { rerender, container } = render(<ErrorAlert error="Pick a file first." />);
    expect(screen.getByRole("alert")).toHaveTextContent("Pick a file first.");
    rerender(<ErrorAlert error={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("never shows raw text for a non-API error", () => {
    render(<ErrorAlert error={new Error("TypeError: x is undefined")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong.");
    expect(screen.queryByText(/undefined/)).not.toBeInTheDocument();
  });
});
