export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string;
}

/** Returned once, at creation — the raw key is never retrievable again. */
export interface ApiKeyCreated extends ApiKey {
  raw_key: string;
}
