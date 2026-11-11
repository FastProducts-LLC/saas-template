// Role is generated from the backend domain enum (scripts/gen_enums.py).
import type { Role } from "../../../shared/api/enums";

export type { Role };

export interface Org {
  id: string;
  name: string;
  slug: string;
  email_domain: string | null;
  created_at: string;
  role: Role;
}

export interface Member {
  id: string; // membership id
  user_id: string;
  email: string;
  name: string;
  role: Role;
  created_at: string;
}

export interface Invitation {
  id: string;
  email: string;
  role: Role;
  expires_at: string;
  created_at: string;
}

/** Roles the org's admin UI can assign (ownership transfers are out of scope). */
export const ASSIGNABLE_ROLES: readonly Role[] = ["admin", "member"];

export function canManageMembers(role: Role | undefined): boolean {
  return role === "owner" || role === "admin";
}
