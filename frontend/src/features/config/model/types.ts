// Shape of GET /api/config — the unauthenticated client bootstrap.
// Flags only; the backend never puts secrets or per-user data here.
export interface AppConfig {
  features: Record<string, boolean>;
}

// Keys the backend knows about (KNOWN_FLAGS in feature_flags/domain/entities.py).
export type FeatureKey = "community";
