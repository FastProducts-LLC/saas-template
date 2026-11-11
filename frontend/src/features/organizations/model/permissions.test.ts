import { describe, expect, it } from "vitest";

import { canEditMemberRole, isAdmin, isOwner } from "./permissions";
import type { Role } from "./types";

const ROLES: Role[] = ["owner", "admin", "member"];

describe("isAdmin", () => {
  it("is true for owner and admin", () => {
    expect(isAdmin("owner")).toBe(true);
    expect(isAdmin("admin")).toBe(true);
  });

  it("is false for member", () => {
    expect(isAdmin("member")).toBe(false);
  });
});

describe("isOwner", () => {
  it("is true only for owner", () => {
    expect(isOwner("owner")).toBe(true);
    expect(isOwner("admin")).toBe(false);
    expect(isOwner("member")).toBe(false);
  });
});

describe("canEditMemberRole", () => {
  // Expected truth table across the full actor x target matrix.
  // Admins can edit anyone except owners; owners can edit anyone;
  // members can edit no one.
  const expected: Record<Role, Record<Role, boolean>> = {
    owner: { owner: true, admin: true, member: true },
    admin: { owner: false, admin: true, member: true },
    member: { owner: false, admin: false, member: false },
  };

  for (const actor of ROLES) {
    for (const target of ROLES) {
      it(`${actor} editing ${target} -> ${expected[actor][target]}`, () => {
        expect(canEditMemberRole(actor, target)).toBe(expected[actor][target]);
      });
    }
  }

  it("lets owners edit other owners but blocks admins from editing owners", () => {
    expect(canEditMemberRole("owner", "owner")).toBe(true);
    expect(canEditMemberRole("admin", "owner")).toBe(false);
  });
});
