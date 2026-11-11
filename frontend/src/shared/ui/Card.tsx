import { type HTMLAttributes, type ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  title?: string;
  children?: ReactNode;
}

// Flat panel used for content sections across billing, settings, and credits.
// An optional title renders as the same heading those pages use.
export default function Card({ title, className = "", children, ...props }: CardProps) {
  return (
    <div className={`rounded border border-[var(--line)] bg-white p-5 ${className}`} {...props}>
      {title && <h2 className="text-base font-semibold text-[var(--ink)]">{title}</h2>}
      {children}
    </div>
  );
}
