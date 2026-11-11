/** Non-essential consent categories. Essential (auth cookie, error
 *  monitoring, the consent record itself) is implicit and always on. */
export interface ConsentCategories {
  analytics: boolean;
}

export interface StoredConsent {
  /** Banner-copy/policy version consented to; bumping re-prompts everyone. */
  version: string;
  decidedAt: string;
  categories: ConsentCategories;
}
