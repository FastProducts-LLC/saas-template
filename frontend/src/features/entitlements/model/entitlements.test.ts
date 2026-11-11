import { describe, expect, it } from "vitest";
import { isIncluded, remaining, isAtLimit, formatLimit } from "./entitlements";
describe("entitlements", () => {
  it("treats null as unlimited", () => {
    expect(isIncluded(null)).toBe(true);
    expect(remaining(null, 100)).toBeNull();
    expect(isAtLimit(null, 100)).toBe(false);
  });
  it("treats zero as not included", () => {
    expect(isIncluded(0)).toBe(false);
    expect(remaining(0, 0)).toBe(0);
    expect(isAtLimit(0, 0)).toBe(true);
  });
  it("reports at-limit only when used reaches the limit", () => {
    expect(isAtLimit(5, 4)).toBe(false);
    expect(isAtLimit(5, 5)).toBe(true);
    expect(isAtLimit(5, 6)).toBe(true);
    expect(remaining(5, 3)).toBe(2);
    expect(remaining(5, 6)).toBe(0);
  });
  it("formats limits for display", () => {
    expect(formatLimit(null)).toBe("Unlimited");
    expect(formatLimit(0)).toBe("0");
    expect(formatLimit(5)).toBe("5");
  });
});
