import type { CreditAction } from "../../credits";
// GenerationStatus is generated from the backend domain enum (scripts/gen_enums.py).
import type { GenerationStatus } from "../../../shared/api/enums";

/** Kinds accepted by POST /orgs/{id}/generations (llm_call goes through /llm). */
export type GenerationKind = Exclude<CreditAction, "llm_call">;

export type { GenerationStatus };

export interface Generation {
  id: string;
  kind: GenerationKind;
  model: string;
  prompt: string;
  status: GenerationStatus;
  credits_cost: number;
  mime_type: string | null;
  /** Catalog copy for a failure (never raw provider text). */
  error: string | null;
  /** Catalog code for a failure, e.g. ERR_GEN_003 — what support needs. */
  error_code: string | null;
  has_file: boolean;
  created_at: string;
  completed_at: string | null;
}

export const TERMINAL_STATUSES: ReadonlySet<GenerationStatus> = new Set([
  "succeeded",
  "failed",
  "canceled",
]);
