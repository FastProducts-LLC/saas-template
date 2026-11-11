import { Link } from "react-router-dom";
import { ROUTES } from "../../../shared/lib/routes";
import { Alert } from "../../../shared/ui";
import { formatLimit } from "../model/entitlements";
export default function UpgradePrompt({
  entitlement,
  limit,
}: {
  entitlement: string;
  limit: number | null;
}) {
  return (
    <Alert tone="info">
      <p>
        {entitlement}:{" "}
        {limit === 0
          ? "Not included in your plan."
          : `Plan limit: ${formatLimit(limit)}. Capacity reached.`}
      </p>
      <Link className="text-[var(--teal-deep)] hover:underline" to={ROUTES.billing}>
        Upgrade your plan in Billing
      </Link>
    </Alert>
  );
}
