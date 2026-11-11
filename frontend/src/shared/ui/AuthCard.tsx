import { type ReactNode } from "react";

import { ROUTES } from "../lib/routes";
import { BRAND } from "../lib/brand";

interface AuthCardProps {
  title?: string;
  children?: ReactNode;
  "data-testid"?: string;
}

// Centered full-screen shell for standalone pages (auth, recovery screens):
// the same layout used by the ErrorBoundary fallback. The optional title
// renders as the page heading the auth pages use.
export default function AuthCard({ title, children, "data-testid": testId }: AuthCardProps) {
  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center bg-[var(--paper)] px-4"
      data-testid={testId}
    >
      <a
        href={ROUTES.home}
        data-testid="auth-card-home-link"
        className="mb-6 font-[family-name:var(--font-display)] text-xl font-bold tracking-tight text-[var(--ink)]"
      >
        {BRAND}
      </a>
      <div className="w-full max-w-sm rounded border border-[var(--line)] bg-white p-8">
        {title && (
          <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight text-[var(--ink)]">
            {title}
          </h1>
        )}
        {children}
      </div>
    </div>
  );
}
