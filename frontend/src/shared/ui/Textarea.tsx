import { forwardRef, useId, type TextareaHTMLAttributes } from "react";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

// Multiline sibling of Input — same field styling, label, and error slot.
const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, error, id, className = "", ...props },
  ref,
) {
  const generatedId = useId();
  const textareaId = id ?? (label ? generatedId : undefined);

  return (
    <div>
      {label && (
        <label htmlFor={textareaId} className="mb-1 block text-sm font-medium text-[var(--slate)]">
          {label}
        </label>
      )}
      <textarea
        ref={ref}
        id={textareaId}
        className={`w-full rounded border border-[var(--line)] bg-white px-3 py-2 text-sm text-[var(--ink)] transition-colors placeholder:text-[var(--slate)]/50 focus:border-[var(--teal)] focus:outline-none focus:ring-2 focus:ring-[var(--teal)]/15 ${className}`}
        {...props}
      />
      {error && <p className="mt-1 text-sm text-[var(--danger)]">{error}</p>}
    </div>
  );
});

export default Textarea;
