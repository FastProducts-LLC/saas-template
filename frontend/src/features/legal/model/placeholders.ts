import { BRAND, BRAND_URL, LEGAL, SUPPORT_EMAIL } from "../../../shared/lib/brand";

export const LEGAL_PLACEHOLDERS: Record<string, string> = {
  company_name: LEGAL.companyName,
  service_name: BRAND,
  website_url: BRAND_URL,
  support_email: SUPPORT_EMAIL,
  effective_date: LEGAL.effectiveDate,
  jurisdiction_state: LEGAL.jurisdictionState,
  jurisdiction_country: LEGAL.jurisdictionCountry,
  arbitration_venue: LEGAL.arbitrationVenue,
  minimum_age: String(LEGAL.minimumAge),
};

export function fillLegalPlaceholders(markdown: string, values = LEGAL_PLACEHOLDERS): string {
  // A callback inserts values literally in one pass, leaving unknown names visible.
  return markdown.replace(/\{\{(\w+)\}\}/g, (placeholder, name: string) =>
    Object.prototype.hasOwnProperty.call(values, name) ? values[name] : placeholder,
  );
}
