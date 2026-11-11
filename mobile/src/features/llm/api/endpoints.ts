import { api } from "../../../shared/api";
import type { LlmCall, LlmProvider } from "../model/types";

export const complete = (orgId: string, provider: LlmProvider, prompt: string, maxTokens = 1024) =>
  api<LlmCall>(`/orgs/${orgId}/llm/complete`, {
    method: "POST",
    body: JSON.stringify({ provider, prompt, max_tokens: maxTokens }),
  });

export const listCalls = (orgId: string, limit = 20, offset = 0) =>
  api<LlmCall[]>(`/orgs/${orgId}/llm/calls?limit=${limit}&offset=${offset}`);

export const getCall = (orgId: string, callId: string) =>
  api<LlmCall>(`/orgs/${orgId}/llm/calls/${callId}`);
