import { UPLOAD_AVATAR_MAX_BYTES } from "../../../shared/lib/policy";

export const AVATAR_FILE_TYPES = ["image/png", "image/jpeg", "image/webp"] as const;
export type AvatarValidation = { ok: true } | { ok: false; reason: "type" | "size" | "empty" };

export function validateAvatarFile(file: File): AvatarValidation {
  if (!AVATAR_FILE_TYPES.some((type) => type === file.type)) return { ok: false, reason: "type" };
  if (file.size === 0) return { ok: false, reason: "empty" };
  if (file.size > UPLOAD_AVATAR_MAX_BYTES) return { ok: false, reason: "size" };
  return { ok: true };
}

export const AVATAR_VALIDATION_MESSAGES = {
  type: "Choose a PNG, JPEG, or WebP image.",
  size: `Choose an image no larger than ${UPLOAD_AVATAR_MAX_BYTES / (1024 * 1024)} MB.`,
  empty: "This file is empty. Choose an image with content.",
};
