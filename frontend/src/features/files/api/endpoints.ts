import { api } from "../../../shared/api";
import type { FilePurpose, StoredFile, UploadCreated, UploadTarget } from "../model/types";

export const createUpload = (purpose: FilePurpose, file: File) =>
  api<UploadCreated>("/files/uploads", {
    method: "POST",
    body: JSON.stringify({ purpose, content_type: file.type, size_bytes: file.size }),
  });

export const confirmUpload = (fileId: string) =>
  api<StoredFile>(`/files/${fileId}/confirm`, { method: "POST" });

export async function putToStorage(upload: UploadTarget, file: File): Promise<void> {
  // Grants authorize the transfer themselves; never attach the app session.
  const response = await fetch(upload.url, {
    method: upload.method,
    headers: upload.headers,
    body: file,
    credentials: "omit",
  });
  if (!response.ok)
    throw new Error(`Photo upload failed (storage status ${response.status}). Please try again.`);
}
