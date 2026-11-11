import { SegmentedControl } from "../../../shared/ui";
import type { BillingInterval } from "../model/types";

const OPTIONS = [
  { value: "monthly", label: "Monthly" },
  { value: "annual", label: "Annual" },
] as const;

export default function PlanIntervalToggle({
  value,
  onChange,
  className = "",
}: {
  value: BillingInterval;
  onChange: (interval: BillingInterval) => void;
  className?: string;
}) {
  return (
    <SegmentedControl
      legend="Billing interval"
      options={OPTIONS}
      value={value}
      onChange={onChange}
      className={className}
    />
  );
}
