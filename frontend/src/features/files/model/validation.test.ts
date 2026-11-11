import { describe, expect, it } from "vitest";
import { UPLOAD_AVATAR_MAX_BYTES } from "../../../shared/lib/policy";
import { validateAvatarFile } from "./validation";

describe("validateAvatarFile", () => {
  it("accepts png, jpeg and webp under the size limit", () => {
    for (const type of ["image/png", "image/jpeg", "image/webp"]) {
      expect(validateAvatarFile(new File(["image"], "photo", { type }))).toEqual({ ok: true });
    }
    expect(
      validateAvatarFile(
        new File([new Uint8Array(UPLOAD_AVATAR_MAX_BYTES)], "photo", { type: "image/png" }),
      ),
    ).toEqual({ ok: true });
  });
  it("rejects other file types", () => {
    expect(validateAvatarFile(new File(["image"], "photo", { type: "image/gif" }))).toEqual({
      ok: false,
      reason: "type",
    });
  });
  it("rejects files over the size limit", () => {
    expect(
      validateAvatarFile(
        new File([new Uint8Array(UPLOAD_AVATAR_MAX_BYTES + 1)], "photo", { type: "image/png" }),
      ),
    ).toEqual({ ok: false, reason: "size" });
  });
  it("rejects empty files", () => {
    expect(validateAvatarFile(new File([], "photo", { type: "image/png" }))).toEqual({
      ok: false,
      reason: "empty",
    });
  });
});
