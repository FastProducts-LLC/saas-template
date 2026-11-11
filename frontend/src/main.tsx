// Self-hosted fonts (GDPR: no requests to fonts.googleapis.com). Weights must
// stay in sync with DESIGN.md's typography spec.
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource-variable/inter";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { AuthProvider } from "./features/auth";
import { ErrorUIProvider } from "./lib/errors";
import { ApiError, publishError } from "./shared/api";
import { initConsentMode } from "./shared/lib/track";
import { initSentry } from "./shared/lib/sentry";
import "./index.css";

initSentry(); // no-op unless VITE_SENTRY_DSN was set at build time
initConsentMode(); // Consent Mode v2: declare denied defaults before any tag loads

const queryClient = new QueryClient({
  // Query failures surface through the global error UI (catalog-routed);
  // mutations are NOT published here — api() already publishes on final
  // failure, and forms additionally bind err.fields/userMessage inline.
  queryCache: new QueryCache({
    onError: (error) => publishError(error),
  }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Catalog-driven retry: only codes with a retry policy re-run, at most
      // `max` times. Non-catalog errors (network blips) get one retry.
      // Mutations never retry here — api() retries them internally, reusing
      // the same Idempotency-Key so a retry can't double-execute.
      retry: (failureCount, error) => {
        if (error instanceof ApiError) {
          return error.retry !== null && failureCount < error.retry.max;
        }
        return failureCount < 1;
      },
      retryDelay: (attempt, error) =>
        error instanceof ApiError && error.retry
          ? error.retry.afterMs * (attempt + 1)
          : Math.min(1_000 * 2 ** attempt, 5_000),
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ErrorUIProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </ErrorUIProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
);
