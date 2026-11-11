import { useId } from "react";

interface SegmentedControlProps<T extends string> {
  /** Accessible group name (rendered as a visually hidden legend). */
  legend: string;
  options: readonly { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
}

// A radio group that looks like a two/three-way switch. Real radio inputs
// keep keyboard and screen-reader behavior; the label is the visible pill.
export default function SegmentedControl<T extends string>({
  legend,
  options,
  value,
  onChange,
  className = "",
}: SegmentedControlProps<T>) {
  const name = useId();
  return (
    <fieldset
      className={`inline-flex rounded border border-[var(--line)] bg-[var(--mist)] p-0.5 ${className}`}
    >
      <legend className="sr-only">{legend}</legend>
      {options.map((option) => {
        const checked = option.value === value;
        return (
          <label
            key={option.value}
            className={`relative cursor-pointer rounded-[3px] px-3 py-1.5 text-[13px] font-medium transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-[var(--teal)]/30 ${
              checked
                ? "bg-white text-[var(--ink)] shadow-[0_0_0_1px_var(--line)]"
                : "text-[var(--slate)] hover:text-[var(--ink)]"
            }`}
          >
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={checked}
              onChange={() => onChange(option.value)}
              className="sr-only"
            />
            {option.label}
          </label>
        );
      })}
    </fieldset>
  );
}
