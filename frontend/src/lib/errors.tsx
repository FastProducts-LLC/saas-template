// Global error UI, driven entirely by the catalog's `display` routing:
//   field  -> ignored here (forms bind err.fields / err.userMessage inline)
//   toast  -> transient toast (severity-styled, copy-details, tech disclosure)
//             — unless a component claims the error for inline display
//             (getErrorMessage / <ErrorAlert>) within INLINE_CLAIM_GRACE_MS
//   banner -> persistent offline banner (auto-retries active queries on reconnect)
//   page   -> full takeover (maintenance polls /api/health and reloads itself;
//             session expiry is handled by the auth layer + login page notice)
//
// Mount once in main.tsx, inside QueryClientProvider:
//   <ErrorUIProvider><App /></ErrorUIProvider>

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { isErrorClaimed, subscribeErrors, type ApiError } from "../shared/api";

const TOAST_TTL_MS: Record<string, number> = {
  info: 6_000,
  warning: 8_000,
  error: 10_000,
  critical: 12_000,
};
const DEDUPE_WINDOW_MS = 2_500;
// How long a toast waits for a component to claim the error inline. The bus
// fires before the caller's catch/onError runs, so the toast must defer; a
// rerender with the error state lands well inside this window.
export const INLINE_CLAIM_GRACE_MS = 150;

interface Toast {
  id: number;
  err: ApiError;
}

let nextToastId = 1;

export function ErrorUIProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [offline, setOffline] = useState(!navigator.onLine);
  const [maintenance, setMaintenance] = useState(false);
  const lastShown = useRef(new Map<string, number>());
  const queryClient = useQueryClient();

  const dismiss = useCallback((id: number) => {
    setToasts((ts) => ts.filter((t) => t.id !== id));
  }, []);

  const pushToast = useCallback(
    (err: ApiError) => {
      const now = Date.now();
      const last = lastShown.current.get(err.code) ?? 0;
      if (now - last < DEDUPE_WINDOW_MS) return; // burst of one failure, one toast
      lastShown.current.set(err.code, now);
      const id = nextToastId++;
      setToasts((ts) => [...ts.slice(-3), { id, err }]);
      setTimeout(() => dismiss(id), TOAST_TTL_MS[err.severity] ?? 8_000);
    },
    [dismiss],
  );

  // Route bus events by catalog display.
  useEffect(
    () =>
      subscribeErrors((err) => {
        if (err.code === "ERR_NET_001") {
          setOffline(true);
          return;
        }
        if (err.code === "ERR_SRV_003") {
          setMaintenance(true);
          return;
        }
        if (err.display === "toast" || err.display === "banner") {
          setTimeout(() => {
            if (!isErrorClaimed(err)) pushToast(err);
          }, INLINE_CLAIM_GRACE_MS);
        }
        // display === "field" / "page": owned by forms / auth+router respectively.
      }),
    [pushToast],
  );

  // Offline detection beyond failed fetches; reconnect refetches what's on screen.
  useEffect(() => {
    const goOffline = () => setOffline(true);
    const goOnline = () => {
      setOffline(false);
      queryClient.refetchQueries({ type: "active" });
    };
    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);
    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online", goOnline);
    };
  }, [queryClient]);

  // A successful request while "offline" (fetch failed but the browser never
  // fired `online`) clears the banner lazily via periodic health probe.
  useEffect(() => {
    if (!offline) return;
    const timer = setInterval(async () => {
      try {
        const res = await fetch("/api/health");
        if (res.ok) {
          setOffline(false);
          queryClient.refetchQueries({ type: "active" });
        }
      } catch {
        // still offline
      }
    }, 5_000);
    return () => clearInterval(timer);
  }, [offline, queryClient]);

  if (maintenance) return <MaintenancePage />;

  return (
    <>
      {offline && <OfflineBanner />}
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2">
        {toasts.map(({ id, err }) => (
          <ErrorToast key={id} err={err} onDismiss={() => dismiss(id)} />
        ))}
      </div>
    </>
  );
}

const SEVERITY_STYLES: Record<string, string> = {
  info: "border-[var(--line)]",
  warning: "border-[var(--info)]",
  error: "border-[var(--danger)]",
  critical: "border-[var(--danger)]",
};

function ErrorToast({ err, onDismiss }: { err: ApiError; onDismiss: () => void }) {
  const [showDetails, setShowDetails] = useState(false);
  const [copied, setCopied] = useState(false);

  async function copyDetails() {
    try {
      await navigator.clipboard.writeText(err.details);
      setCopied(true);
      setTimeout(() => setCopied(false), 1_500);
    } catch {
      // clipboard blocked — the reference is still visible to copy by hand
    }
  }

  return (
    <div
      role="alert"
      data-testid="toast"
      data-code={err.code}
      className={`pointer-events-auto rounded border bg-[var(--paper)] p-4 shadow-[2px_2px_0_var(--line)] ${SEVERITY_STYLES[err.severity] ?? "border-[var(--line)]"}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-[var(--ink)]">{err.userMessage}</p>
          <p className="mt-1 text-sm text-[var(--slate)]">{err.actionStep}</p>
        </div>
        <button
          onClick={onDismiss}
          aria-label="Dismiss"
          data-testid="toast-dismiss-button"
          className="shrink-0 text-[var(--slate)]/55 hover:text-[var(--slate)]"
        >
          ✕
        </button>
      </div>
      <div className="mt-2 flex items-center gap-3 text-xs text-[var(--slate)]/55">
        <span className="font-mono">{err.reference}</span>
        <button
          onClick={copyDetails}
          data-testid="toast-copy-button"
          className="text-[var(--teal)] hover:underline"
        >
          {copied ? "Copied" : "Copy details"}
        </button>
        <button
          onClick={() => setShowDetails((s) => !s)}
          data-testid="toast-details-button"
          className="text-[var(--slate)]/55 hover:underline"
        >
          {showDetails ? "Hide" : "Technical details"}
        </button>
      </div>
      {showDetails && (
        <p
          data-testid="toast-details"
          className="mt-2 break-all font-mono text-xs text-[var(--slate)]/75"
        >
          HTTP {err.status} — {err.message}
        </p>
      )}
    </div>
  );
}

function OfflineBanner() {
  return (
    <div
      role="status"
      data-testid="error-banner"
      className="sticky top-0 z-50 border-b border-[var(--line)] bg-[var(--mist)] px-4 py-2 text-center text-sm text-[var(--ink)]"
    >
      We can't reach the internet right now. Check your connection — we'll retry automatically.
    </div>
  );
}

function MaintenancePage() {
  // Poll /api/health with gentle backoff; reload the app the moment it's back.
  useEffect(() => {
    let delay = 5_000;
    let timer: ReturnType<typeof setTimeout>;
    const probe = async () => {
      try {
        const res = await fetch("/api/health");
        if (res.ok) {
          window.location.reload();
          return;
        }
      } catch {
        // still down
      }
      delay = Math.min(delay * 1.5, 30_000);
      timer = setTimeout(probe, delay);
    };
    timer = setTimeout(probe, delay);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div
      data-testid="maintenance-takeover"
      className="flex min-h-screen flex-col items-center justify-center bg-[var(--paper)] px-4 text-center"
    >
      <h1 className="text-xl font-semibold text-[var(--ink)]">
        We're doing some quick maintenance and will be right back.
      </h1>
      <p className="mt-2 text-sm text-[var(--slate)]">
        Nothing to fix on your end — this page will refresh itself when we're done.
      </p>
    </div>
  );
}
