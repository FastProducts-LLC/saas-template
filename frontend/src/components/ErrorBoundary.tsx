// Top-level error boundary: a render crash shows a recoverable screen instead
// of a blank page. Errors are reported to Sentry (no-ops without a DSN) in
// addition to being logged to the console.

import { Component, type ErrorInfo, type ReactNode } from "react";
import * as Sentry from "@sentry/react";

import { AuthCard, Button } from "../shared/ui";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Error-tracking hook point: report to Sentry and keep the console log.
    Sentry.captureException(error, {
      contexts: { react: { componentStack: info.componentStack } },
    });
    console.error("Unhandled render error:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <AuthCard>
          <div data-testid="error-boundary" className="text-center">
            <h1 className="text-xl font-semibold text-[var(--ink)]">Something went wrong</h1>
            <p className="mt-2 text-sm text-[var(--slate)]/75">
              An unexpected error occurred. Reloading usually fixes it.
            </p>
            <Button
              data-testid="error-boundary-reload-button"
              onClick={() => window.location.reload()}
              className="mt-6 w-full"
            >
              Reload page
            </Button>
          </div>
        </AuthCard>
      );
    }
    return this.props.children;
  }
}
