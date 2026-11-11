import { useId, type InputHTMLAttributes, type SVGProps } from "react";

function EyeIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
      <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

interface PasswordInputProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "type" | "value" | "onChange"
> {
  label?: string;
  error?: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  show: boolean;
  onToggle: () => void;
  showLabel?: string;
  hideLabel?: string;
  "data-testid"?: string;
}

export default function PasswordInput({
  label,
  error,
  id,
  placeholder,
  value,
  onChange,
  show,
  onToggle,
  showLabel = "Show password",
  hideLabel = "Hide password",
  required = true,
  className = "",
  "aria-describedby": ariaDescribedBy,
  "data-testid": testId,
  ...props
}: PasswordInputProps) {
  const generatedId = useId();
  const inputId = id ?? (label ? generatedId : undefined);
  const errorId = error && inputId ? `${inputId}-error` : undefined;
  const describedBy = [ariaDescribedBy, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div>
      {label && (
        <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-[var(--slate)]">
          {label}
        </label>
      )}
      <div className="relative">
        <input
          {...props}
          id={inputId}
          type={show ? "text" : "password"}
          required={required}
          placeholder={placeholder}
          value={value}
          aria-describedby={describedBy}
          aria-invalid={error ? "true" : undefined}
          data-testid={testId}
          onChange={(e) => onChange(e.target.value)}
          className={`w-full rounded border border-[var(--line)] bg-white px-3 py-2 pr-10 text-sm text-[var(--ink)] transition-colors placeholder:text-[var(--slate)]/50 focus:border-[var(--teal)] focus:outline-none focus:ring-2 focus:ring-[var(--teal)]/15 ${className}`}
        />
        <button
          type="button"
          onClick={onToggle}
          data-testid={testId ? `${testId}-toggle` : undefined}
          aria-controls={inputId}
          aria-label={show ? hideLabel : showLabel}
          className="absolute inset-y-0 right-0 flex items-center pr-3 text-[var(--slate)]/55 transition-colors hover:text-[var(--slate)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--teal)]/30"
        >
          {show ? <EyeOffIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
        </button>
      </div>
      {error && (
        <p id={errorId} className="mt-1 text-sm text-[var(--danger)]">
          {error}
        </p>
      )}
    </div>
  );
}
