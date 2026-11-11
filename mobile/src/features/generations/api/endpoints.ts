import { api, apiDataUri } from "../../../shared/api";
import type { Generation, GenerationKind } from "../model/types";

export const createGeneration = (orgId: string, kind: GenerationKind, prompt: string) =>
  api<Generation>(`/orgs/${orgId}/generations`, {
    method: "POST",
    body: JSON.stringify({ kind, prompt }),
  });

export const listGenerations = (orgId: string, limit = 20, offset = 0) =>
  api<Generation[]>(`/orgs/${orgId}/generations?limit=${limit}&offset=${offset}`);

export const getGeneration = (orgId: string, generationId: string) =>
  api<Generation>(`/orgs/${orgId}/generations/${generationId}`);

export const cancelGeneration = (orgId: string, generationId: string) =>
  api<Generation>(`/orgs/${orgId}/generations/${generationId}/cancel`, { method: "POST" });

export const deleteGeneration = (orgId: string, generationId: string) =>
  api<void>(`/orgs/${orgId}/generations/${generationId}`, { method: "DELETE" });

/** Authed download of the result asset as a data URI for <Image>. */
export const getGenerationFile = (orgId: string, generationId: string) =>
  apiDataUri(`/orgs/${orgId}/generations/${generationId}/file`);
