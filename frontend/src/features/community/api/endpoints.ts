import { api } from "../../../shared/api";
import type {
  CommunityPlan,
  Conversation,
  DirectoryPage,
  JoinPayload,
  Message,
  MessagePage,
  MyCommunity,
  Member,
  Plan,
  CommunityProfile,
  ProfileUpdatePayload,
} from "../model/types";

export const getMyCommunity = () => api<MyCommunity>("/community/me");

export const joinCommunity = (payload: JoinPayload) =>
  api<MyCommunity>("/community/profile", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const updateProfile = (payload: ProfileUpdatePayload) =>
  api<CommunityProfile>("/community/profile", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

export const listMembers = (search: string, page: number) =>
  api<DirectoryPage>(`/community/members?search=${encodeURIComponent(search)}&page=${page}`);

export const getMember = (handle: string) =>
  api<Member>(`/community/members/${encodeURIComponent(handle)}`);

export const listPlans = () => api<Plan[]>("/community/plans");

export const createMembershipCheckout = (plan: CommunityPlan) =>
  api<{ url: string }>("/community/membership/checkout", {
    method: "POST",
    body: JSON.stringify({ plan }),
  });

export const createMembershipPortal = () =>
  api<{ url: string }>("/community/membership/portal", { method: "POST" });

export const listConversations = () => api<Conversation[]>("/community/conversations");

export const startConversation = (recipientHandle: string) =>
  api<Conversation>("/community/conversations", {
    method: "POST",
    body: JSON.stringify({ recipient_handle: recipientHandle }),
  });

export const listMessages = (conversationId: string) =>
  api<MessagePage>(`/community/conversations/${conversationId}/messages`);

export const sendMessage = (conversationId: string, body: string) =>
  api<Message>(`/community/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });

export const markConversationRead = (conversationId: string) =>
  api<void>(`/community/conversations/${conversationId}/read`, {
    method: "POST",
  });

export const setAvatar = (fileId: string) =>
  api<CommunityProfile>("/community/profile/avatar", {
    method: "PUT",
    body: JSON.stringify({ file_id: fileId }),
  });

export const removeAvatar = () => api<void>("/community/profile/avatar", { method: "DELETE" });
