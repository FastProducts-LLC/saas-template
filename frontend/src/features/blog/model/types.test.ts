import { describe, expect, it } from "vitest";

import { parseTagsInput } from "./types";

describe("parseTagsInput", () => {
  it("lowercases, slugifies, and trims", () => {
    expect(parseTagsInput("  Product Launch , Eng ")).toEqual(["product-launch", "eng"]);
  });

  it("dedupes preserving first-seen order", () => {
    expect(parseTagsInput("alpha, Beta, alpha, BETA")).toEqual(["alpha", "beta"]);
  });

  it("drops empties and caps at 5", () => {
    expect(parseTagsInput("a, b, , c, d, e, f, g")).toEqual(["a", "b", "c", "d", "e"]);
  });
});
