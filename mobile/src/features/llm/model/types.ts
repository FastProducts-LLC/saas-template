export type LlmProvider = "gemini" | "openai" | "anthropic";

export type LlmCallStatus = "pending" | "succeeded" | "failed";

export interface LlmCall {
  id: string;
  provider: LlmProvider;
  model: string;
  prompt: string;
  status: LlmCallStatus;
  response_text: string | null;
  tokens_in: number;
  tokens_out: number;
  credits_cost: number;
  /** Catalog copy for a failure (never raw provider text). */
  error: string | null;
  /** Catalog code for a failure, e.g. ERR_GEN_003 — what support needs. */
  error_code: string | null;
  created_at: string;
  completed_at: string | null;
}

export const LLM_TERMINAL_STATUSES: ReadonlySet<LlmCallStatus> = new Set([
  "succeeded",
  "failed",
]);

export const PROVIDERS: readonly { value: LlmProvider; label: string }[] = [
  { value: "gemini", label: "Gemini" },
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Claude" },
];
