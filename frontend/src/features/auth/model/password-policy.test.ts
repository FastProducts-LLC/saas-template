import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { passwordMeetsRules, validatePassword } from "./password-policy";

// The project's vitest config doesn't enable `globals`, so Testing Library's
// automatic per-test cleanup isn't registered — do it explicitly here. (This
// file renders nothing, but the convention is applied uniformly.)
afterEach(cleanup);

describe("validatePassword", () => {
  it("requires at least 12 characters for the length rule", () => {
    expect(validatePassword("abcd1234").length).toBe(false);
    expect(validatePassword("abcdefghijk1").length).toBe(true);
  });

  it("requires both letters and digits for the mix rule", () => {
    expect(validatePassword("abcdefghijkl").mix).toBe(false);
    expect(validatePassword("123456789012").mix).toBe(false);
    expect(validatePassword("abcdefghijk1").mix).toBe(true);
  });

  it("flags an empty password as not satisfying notCommon", () => {
    expect(validatePassword("").notCommon).toBe(false);
  });

  it("rejects commonly used passwords via notCommon", () => {
    expect(validatePassword("password123").notCommon).toBe(false);
    expect(validatePassword("Password123").notCommon).toBe(false); // case-insensitive
    expect(validatePassword("12345678").notCommon).toBe(false);
  });

  it("accepts an uncommon password via notCommon", () => {
    expect(validatePassword("zephyr92mango").notCommon).toBe(true);
  });

  it("returns all rules satisfied for a strong password", () => {
    const rules = validatePassword("zephyr92mango");
    expect(rules).toEqual({ length: true, mix: true, notCommon: true });
  });
});

describe("passwordMeetsRules", () => {
  it("is true only when every rule passes", () => {
    expect(passwordMeetsRules({ length: true, mix: true, notCommon: true })).toBe(true);
  });

  it("is false when any single rule fails", () => {
    expect(passwordMeetsRules({ length: false, mix: true, notCommon: true })).toBe(false);
    expect(passwordMeetsRules({ length: true, mix: false, notCommon: true })).toBe(false);
    expect(passwordMeetsRules({ length: true, mix: true, notCommon: false })).toBe(false);
  });

  it("agrees with validatePassword end to end", () => {
    expect(passwordMeetsRules(validatePassword("zephyr92mango"))).toBe(true);
    expect(passwordMeetsRules(validatePassword("short1"))).toBe(false);
    expect(passwordMeetsRules(validatePassword("password123"))).toBe(false);
  });
});
