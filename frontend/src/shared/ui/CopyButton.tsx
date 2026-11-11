import { useEffect, useRef, useState } from "react";

// Small clipboard icon button that copies `value` and flashes a check mark.
export default function CopyButton({
  value,
  label = "Copy",
  "data-testid": testId,
}: {
  value: string;
  label?: string;
  "data-testid"?: string;
}) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard unavailable (permissions/insecure context) — silently no-op.
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      data-testid={testId}
      data-copied={copied || undefined}
      aria-label={copied ? "Copied" : label}
      title={copied ? "Copied" : label}
      className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-[var(--slate)]/40 transition-colors hover:text-[var(--teal-deep)] focus:outline-none focus-visible:text-[var(--teal-deep)]"
    >
      {copied ? (
        <svg
          viewBox="0 0 16 16"
          fill="none"
          className="h-3.5 w-3.5 text-[var(--teal-deep)]"
          aria-hidden="true"
        >
          <path
            d="M3 8.5 6.5 12 13 4.5"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ) : (
        <svg viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5" aria-hidden="true">
          <rect
            x="5.5"
            y="5.5"
            width="8"
            height="8"
            rx="1.5"
            stroke="currentColor"
            strokeWidth="1.4"
          />
          <path
            d="M10.5 5.5V4a1.5 1.5 0 0 0-1.5-1.5H4A1.5 1.5 0 0 0 2.5 4v5A1.5 1.5 0 0 0 4 10.5h1.5"
            stroke="currentColor"
            strokeWidth="1.4"
          />
        </svg>
      )}
    </button>
  );
}
