import { describe, expect, it } from "vitest";
import { formatLimit, isAtLimit, isIncluded, remaining } from "./entitlements";
import type { Entitlement } from "./types";

const entry = (limit: number | null, used = 0): Entitlement => ({
  key: "seats", limit, used, included: limit !== 0, source: "plan", expires_at: null,
});

describe("entitlements", () => {
  it("treats null as unlimited", () => {
    expect(isIncluded(entry(null, 100))).toBe(true);
    expect(isAtLimit(entry(null, 100))).toBe(false);
    expect(remaining(entry(null, 100))).toBeNull();
  });
  it("treats zero as not included", () => {
    expect(isIncluded(entry(0))).toBe(false);
    expect(isAtLimit(entry(0))).toBe(true);
    expect(remaining(entry(0))).toBe(0);
  });
  it("reports at-limit only when used reaches the limit", () => {
    expect(isIncluded(entry(5, 4))).toBe(true);
    expect(isAtLimit(entry(5, 4))).toBe(false);
    expect(remaining(entry(5, 4))).toBe(1);
    expect(isAtLimit(entry(5, 5))).toBe(true);
    expect(remaining(entry(5, 5))).toBe(0);
    expect(isAtLimit(entry(5, 6))).toBe(true);
    expect(remaining(entry(5, 6))).toBe(0);
  });
  it("formats limits for display", () => {
    expect(formatLimit(null)).toBe("Unlimited");
    expect(formatLimit(0)).toBe("0");
    expect(formatLimit(25)).toBe("25");
    expect(formatLimit(1000)).toBe("1,000");
  });
});
