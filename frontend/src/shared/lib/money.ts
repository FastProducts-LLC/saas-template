// The single cents → currency-string formatter. Components must not
// hand-roll `(cents / 100).toFixed(...)` — call this instead.
export function formatMoney(
  cents: number,
  { currency = "USD", fractionDigits }: { currency?: string; fractionDigits?: number } = {},
): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currency.toUpperCase(),
    ...(fractionDigits !== undefined && {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    }),
  }).format(cents / 100);
}
