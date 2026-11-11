import { useEffect } from "react";

import { ApiError, claimError, fieldLabel } from "../api";
import Alert from "./Alert";

interface ErrorAlertProps {
  /** Anything a mutation/query/catch block produced — ApiError, string, or unknown. */
  error: unknown;
  /** Set when the form already renders `error.fields` next to its inputs. */
  hideFields?: boolean;
  className?: string;
  "data-testid"?: string;
}

/**
 * Inline error for forms and panels: catalog headline, the one next step,
 * any per-field problems the form doesn't bind itself, and the support
 * reference (`code · ref`). Rendering it claims the error, so the global
 * toast for the same failure is suppressed (see shared/api/errors.ts).
 */
export default function ErrorAlert({
  error,
  hideFields = false,
  className = "",
  "data-testid": testId = "error-alert",
}: ErrorAlertProps) {
  // Claim during render too: the toast's grace window may close before effects run.
  claimError(error);
  useEffect(() => claimError(error), [error]);

  if (error === null || error === undefined || error === false || error === "") return null;

  if (!(error instanceof ApiError)) {
    const text = typeof error === "string" ? error : "Something went wrong.";
    return (
      <Alert tone="error" className={className} data-testid={testId}>
        {text}
      </Alert>
    );
  }

  const fieldEntries = hideFields ? [] : Object.entries(error.fields);
  return (
    <Alert tone="error" className={className} data-testid={testId}>
      <p className="font-medium" data-testid={`${testId}-message`}>
        {error.userMessage}
      </p>
      {fieldEntries.length > 0 && (
        <ul className="mt-1 list-disc pl-5" data-testid={`${testId}-fields`}>
          {fieldEntries.map(([key, message]) => {
            const label = fieldLabel(key);
            return <li key={key}>{label ? `${label}: ${message}` : message}</li>;
          })}
        </ul>
      )}
      <p className="mt-1 text-[var(--slate)]">{error.actionStep}</p>
      <p className="mt-1 font-mono text-xs text-[var(--slate)]/60" data-testid={`${testId}-ref`}>
        {error.reference}
      </p>
    </Alert>
  );
}
