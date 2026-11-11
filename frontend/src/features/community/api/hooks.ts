import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { EVENTS } from "../../../shared/lib/events";
import { track } from "../../../shared/lib/track";
import * as endpoints from "./endpoints";
import { communityKeys } from "./keys";
import type { CommunityPlan, JoinPayload, MyCommunity, ProfileUpdatePayload } from "../model/types";

export function useMyCommunity(options?: { pollUntilPremium?: boolean }) {
  return useQuery({
    queryKey: communityKeys.me,
    queryFn: endpoints.getMyCommunity,
    // After the Stripe redirect the upgrade only lands when the webhook
    // does — poll briefly until is_premium flips, then stop.
    refetchInterval: options?.pollUntilPremium
      ? (query) => (query.state.data?.membership?.is_premium ? false : 2000)
      : undefined,
  });
}

export function useJoinCommunity() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: JoinPayload) => endpoints.joinCommunity(payload),
    onSuccess: (data: MyCommunity) => {
      track(EVENTS.community_joined);
      queryClient.setQueryData(communityKeys.me, data);
      return queryClient.invalidateQueries({ queryKey: communityKeys.all });
    },
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProfileUpdatePayload) => endpoints.updateProfile(payload),
    onSuccess: () => {
      track(EVENTS.community_profile_updated);
      return queryClient.invalidateQueries({ queryKey: communityKeys.all });
    },
  });
}

export function useDirectory(search: string, page: number) {
  return useQuery({
    queryKey: communityKeys.directory(search, page),
    queryFn: () => endpoints.listMembers(search, page),
    placeholderData: (previous) => previous,
  });
}

export function useMember(handle: string | undefined) {
  return useQuery({
    queryKey: communityKeys.member(handle!),
    queryFn: () => endpoints.getMember(handle!),
    enabled: !!handle,
  });
}

export function usePlans() {
  return useQuery({
    queryKey: communityKeys.plans,
    queryFn: endpoints.listPlans,
    staleTime: 5 * 60_000,
  });
}

export function useMembershipCheckout() {
  return useMutation({
    mutationFn: (plan: CommunityPlan) => endpoints.createMembershipCheckout(plan),
    onSuccess: ({ url }, plan) => {
      // Intent only — activation is the server-truth
      // `community_subscription_activated` event from the Stripe webhook.
      track(EVENTS.checkout_started, { product: "community", plan });
      window.location.href = url;
    },
  });
}

export function useMembershipPortal() {
  return useMutation({
    mutationFn: endpoints.createMembershipPortal,
    onSuccess: ({ url }) => {
      track(EVENTS.billing_portal_opened, { product: "community" });
      window.location.href = url;
    },
  });
}

export function useConversations(options?: { poll?: boolean }) {
  return useQuery({
    queryKey: communityKeys.conversations,
    queryFn: endpoints.listConversations,
    refetchInterval: options?.poll ? 15_000 : undefined,
  });
}

export function useMessages(conversationId: string | undefined) {
  return useQuery({
    queryKey: communityKeys.messages(conversationId!),
    queryFn: () => endpoints.listMessages(conversationId!),
    enabled: !!conversationId,
    // The template's async pattern is polling, not websockets.
    refetchInterval: 5_000,
  });
}

export function useStartConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (recipientHandle: string) => endpoints.startConversation(recipientHandle),
    onSuccess: () => {
      // No recipient handle — who talks to whom is not analytics data.
      track(EVENTS.community_conversation_started);
      return queryClient.invalidateQueries({ queryKey: communityKeys.conversations });
    },
  });
}

export function useSendMessage(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => endpoints.sendMessage(conversationId, body),
    onSuccess: () => {
      track(EVENTS.community_message_sent); // never the body or conversation id
      queryClient.invalidateQueries({
        queryKey: communityKeys.messages(conversationId),
      });
      return queryClient.invalidateQueries({
        queryKey: communityKeys.conversations,
      });
    },
  });
}

export function useMarkConversationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (conversationId: string) => endpoints.markConversationRead(conversationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: communityKeys.conversations }),
  });
}

export function useSetAvatar() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: endpoints.setAvatar,
    onSuccess: (profile, fileId) => {
      queryClient.setQueryData<MyCommunity>(communityKeys.me, (old) =>
        old ? { ...old, profile } : old,
      );
      track(EVENTS.avatar_uploaded, { file_id: fileId });
      return queryClient.invalidateQueries({ queryKey: communityKeys.all });
    },
  });
}

export function useRemoveAvatar() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: endpoints.removeAvatar,
    onSuccess: () => {
      queryClient.setQueryData<MyCommunity>(communityKeys.me, (old) =>
        old?.profile ? { ...old, profile: { ...old.profile, avatar_url: null } } : old,
      );
      return queryClient.invalidateQueries({ queryKey: communityKeys.all });
    },
  });
}
