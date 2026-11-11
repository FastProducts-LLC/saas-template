import { api } from "../../../shared/api";

import type { Invitation, Member, Org, Role } from "../model/types";

export const listOrgs = () => api<Org[]>("/orgs");

export const createOrg = (payload: { name: string; intended_use: string }) =>
  api<Org>("/orgs", { method: "POST", body: JSON.stringify(payload) });

export const renameOrg = (orgId: string, name: string) =>
  api<Org>(`/orgs/${orgId}`, { method: "PATCH", body: JSON.stringify({ name }) });

export const deleteOrg = (orgId: string) => api<void>(`/orgs/${orgId}`, { method: "DELETE" });

export const setOrgDomain = (orgId: string, domain: string | null) =>
  api<Org>(`/orgs/${orgId}/domain`, { method: "PUT", body: JSON.stringify({ domain }) });

export const listMembers = (orgId: string) => api<Member[]>(`/orgs/${orgId}/members`);

export const changeMemberRole = (orgId: string, membershipId: string, role: Role) =>
  api<Member>(`/orgs/${orgId}/members/${membershipId}`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });

export const removeMember = (orgId: string, membershipId: string) =>
  api<void>(`/orgs/${orgId}/members/${membershipId}`, { method: "DELETE" });

export const listInvitations = (orgId: string) => api<Invitation[]>(`/orgs/${orgId}/invitations`);

export const createInvitation = (orgId: string, email: string, role: Role) =>
  api<Invitation>(`/orgs/${orgId}/invitations`, {
    method: "POST",
    body: JSON.stringify({ email, role }),
  });

export const revokeInvitation = (orgId: string, invitationId: string) =>
  api<void>(`/orgs/${orgId}/invitations/${invitationId}`, { method: "DELETE" });

export const acceptInvitation = (token: string) =>
  api<Org>("/invitations/accept", { method: "POST", body: JSON.stringify({ token }) });
