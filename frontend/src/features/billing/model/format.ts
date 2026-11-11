import { formatMoney } from "../../../shared/lib/money";

/** Whole-dollar plan prices drop the cents ("$29"); anything else keeps them. */
export function formatPlanPrice(cents: number): string {
  return formatMoney(cents, { fractionDigits: cents % 100 === 0 ? 0 : 2 });
}
