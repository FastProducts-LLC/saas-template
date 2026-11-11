export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string;
}

export interface ApiKeyCreated extends ApiKey {
  raw_key: string;
}

export interface ApiKeyCreatePayload {
  name: string;
}
