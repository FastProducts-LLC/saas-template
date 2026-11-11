// Pure role/permission rules — the single source of truth for who can do what.

import type { Role } from "./types";

export const isAdmin = (role: Role) => role === "owner" || role === "admin";

export const isOwner = (role: Role) => role === "owner";

/** Admins can edit anyone except owners; owners can edit anyone. */
export const canEditMemberRole = (actor: Role, target: Role) =>
  isAdmin(actor) && (isOwner(actor) || target !== "owner");
