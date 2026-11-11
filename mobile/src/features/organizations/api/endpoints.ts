import { api } from "../../../shared/api";
import type { Invitation, Member, Org, Role } from "../model/types";

export const listOrgs = () => api<Org[]>("/orgs");

export const createOrg = (payload: { name: string; intended_use: string }) =>
  api<Org>("/orgs", { method: "POST", body: JSON.stringify(payload) });

export const listMembers = (orgId: string) => api<Member[]>(`/orgs/${orgId}/members`);

export const changeMemberRole = (orgId: string, membershipId: string, role: Role) =>
  api<Member>(`/orgs/${orgId}/members/${membershipId}`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });

export const removeMember = (orgId: string, membershipId: string) =>
  api<void>(`/orgs/${orgId}/members/${membershipId}`, { method: "DELETE" });

export const listInvitations = (orgId: string) =>
  api<Invitation[]>(`/orgs/${orgId}/invitations`);

export const inviteMember = (orgId: string, email: string, role: Role) =>
  api<Invitation>(`/orgs/${orgId}/invitations`, {
    method: "POST",
    body: JSON.stringify({ email, role }),
  });

export const revokeInvitation = (orgId: string, invitationId: string) =>
  api<void>(`/orgs/${orgId}/invitations/${invitationId}`, { method: "DELETE" });
