import { Link } from "react-router-dom";

// Brand constants live in shared/lib/brand.ts (single source of truth).
import { ROUTES } from "../../../shared/lib/routes";
import { BRAND } from "../../../shared/lib/brand";

// "display" is the app wordmark (Syne); "marketing" is the public-site
// wordmark set in the design-system sans (DESIGN.md "Typography").
const VARIANTS = {
  display: "font-[family-name:var(--font-display)] text-xl font-bold tracking-tight",
  marketing:
    "font-[family-name:var(--font-marketing)] text-[19px] font-semibold tracking-[-0.03em]",
} as const;

export default function BrandMark({
  className = "",
  variant = "display",
  "data-testid": testId,
}: {
  className?: string;
  variant?: keyof typeof VARIANTS;
  "data-testid"?: string;
}) {
  return (
    <Link to={ROUTES.home} data-testid={testId} className={`${VARIANTS[variant]} ${className}`}>
      {BRAND}
    </Link>
  );
}
