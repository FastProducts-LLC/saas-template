import { forwardRef, useId, type InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

// Standard text input matching the auth/settings field styling. Renders an
// optional label above and an error message below. A stable id is generated
// from useId when a label is present and no id is supplied.
const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, id, className = "", ...props },
  ref,
) {
  const generatedId = useId();
  const inputId = id ?? (label ? generatedId : undefined);

  return (
    <div>
      {label && (
        <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-[var(--slate)]">
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={inputId}
        className={`w-full rounded border border-[var(--line)] bg-white px-3 py-2 text-sm text-[var(--ink)] transition-colors placeholder:text-[var(--slate)]/50 focus:border-[var(--teal)] focus:outline-none focus:ring-2 focus:ring-[var(--teal)]/15 ${className}`}
        {...props}
      />
      {error && <p className="mt-1 text-sm text-[var(--danger)]">{error}</p>}
    </div>
  );
});

export default Input;
