import type { FilePurpose, StoredFileStatus } from "../../../shared/api/enums";

export type { FilePurpose };
export interface UploadTarget {
  url: string;
  method: string;
  headers: Record<string, string>;
  expires_at: string;
}
export interface UploadCreated {
  file_id: string;
  upload: UploadTarget;
}
export interface StoredFile {
  id: string;
  purpose: FilePurpose;
  content_type: string;
  size_bytes: number | null;
  status: StoredFileStatus;
  url: string;
}
