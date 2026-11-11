// Org members & invitations. Admin/owner get invite + role/remove controls;
// members see the roster read-only (mirrors the backend's role gates).

import { formatLimit, isAtLimit, PLAN_LIMIT_MESSAGE, useEntitlements } from "../../features/entitlements";

import { useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { useSession } from "../../features/auth";
import {
  ASSIGNABLE_ROLES,
  canManageMembers,
  useChangeMemberRole,
  useCurrentOrg,
  useInvitations,
  useInviteMember,
  useMembers,
  useRemoveMember,
  useRevokeInvitation,
  type Member,
  type Role,
} from "../../features/organizations";
import { Button, Empty, ErrorNote, Field, Rule, SectionTitle, Stamp } from "../../shared/ui/primitives";
import { colors, spacing, type } from "../../shared/ui/theme";

export default function MembersScreen() {
  const { user } = useSession();
  const { org } = useCurrentOrg();
  const entitlements = useEntitlements(org?.id);
  const entitlement = entitlements.data?.entitlements.find((item) => item.key === "seats");
  const atLimit = entitlement ? isAtLimit(entitlement) : false;
  const manage = canManageMembers(org?.role);

  const members = useMembers(org?.id);
  const invitations = useInvitations(org?.id, manage);
  const invite = useInviteMember(org?.id);
  const changeRole = useChangeMemberRole(org?.id);
  const remove = useRemoveMember(org?.id);
  const revoke = useRevokeInvitation(org?.id);

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("member");

  if (!org) {
    return (
      <View style={styles.screen}>
        <Empty message="Create an organization first." />
      </View>
    );
  }

  const confirmRemove = (member: Member) => {
    const self = member.user_id === user?.id;
    Alert.alert(
      self ? "Leave organization?" : `Remove ${member.name || member.email}?`,
      self ? "You will lose access to this organization." : "They will lose access immediately.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: self ? "Leave" : "Remove",
          style: "destructive",
          onPress: () => remove.mutate(member.id),
        },
      ],
    );
  };

  const cycleRole = (member: Member) => {
    if (member.role === "owner") return; // ownership isn't reassigned here
    const next: Role = member.role === "admin" ? "member" : "admin";
    changeRole.mutate({ membershipId: member.id, role: next });
  };

  return (
    <ScrollView style={{ backgroundColor: colors.paper }} contentContainerStyle={styles.screen}>
      {entitlement ? (
        <Text style={styles.memberMeta}>
          Seats: {entitlement.used.toLocaleString()} / {formatLimit(entitlement.limit)}
        </Text>
      ) : null}
      {entitlements.isPending ? <Text style={styles.memberMeta}>Loading plan limits…</Text> : null}
      {entitlements.isError ? <ErrorNote error={entitlements.error} /> : null}
      {atLimit ? <Text style={styles.memberMeta}>{PLAN_LIMIT_MESSAGE}</Text> : null}

      <SectionTitle>
        Members {members.data ? `(${members.data.length})` : ""}
      </SectionTitle>
      {(members.data ?? []).map((m) => (
        <View key={m.id} style={styles.memberRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.memberName}>
              {m.name || m.email}
              {m.user_id === user?.id ? "  (you)" : ""}
            </Text>
            <Text style={styles.memberMeta}>{m.email}</Text>
          </View>
          {manage && m.role !== "owner" ? (
            <Pressable onPress={() => cycleRole(m)} style={styles.roleButton}>
              <Text style={styles.roleButtonText}>{m.role} ⇄</Text>
            </Pressable>
          ) : (
            <Stamp label={m.role} tone={m.role === "owner" ? "match" : "neutral"} />
          )}
          {manage && m.role !== "owner" ? (
            <Pressable onPress={() => confirmRemove(m)} hitSlop={8}>
              <Text style={styles.removeText}>Remove</Text>
            </Pressable>
          ) : null}
        </View>
      ))}
      {changeRole.isError ? <ErrorNote error={changeRole.error} /> : null}
      {remove.isError ? <ErrorNote error={remove.error} /> : null}

      {manage ? (
        <View>
          <View style={{ height: spacing.md }} />
          <Rule />
          <SectionTitle>Invite</SectionTitle>
          <Field
            label="Email"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
          />
          <View style={styles.roleRow}>
            {ASSIGNABLE_ROLES.map((r) => {
              const active = r === role;
              return (
                <Pressable
                  key={r}
                  onPress={() => setRole(r)}
                  style={[styles.rolePick, active && styles.rolePickActive]}
                >
                  <Text style={[styles.rolePickText, active && { color: colors.white }]}>{r}</Text>
                </Pressable>
              );
            })}
          </View>
          <Button
            title="Send invitation"
            busy={invite.isPending}
            disabled={!email.trim() || !entitlement || atLimit}
            onPress={() =>
              invite.mutate({ email: email.trim(), role }, { onSuccess: () => setEmail("") })
            }
          />
          {invite.isError ? <ErrorNote error={invite.error} /> : null}

          <SectionTitle>Pending invitations</SectionTitle>
          {(invitations.data ?? []).map((inv) => (
            <View key={inv.id} style={styles.memberRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.memberName}>{inv.email}</Text>
                <Text style={styles.memberMeta}>
                  {inv.role} · expires {new Date(inv.expires_at).toLocaleDateString()}
                </Text>
              </View>
              <Pressable onPress={() => revoke.mutate(inv.id)} hitSlop={8}>
                <Text style={styles.removeText}>Revoke</Text>
              </Pressable>
            </View>
          ))}
          {invitations.data?.length === 0 ? <Empty message="No pending invitations." /> : null}
          {revoke.isError ? <ErrorNote error={revoke.error} /> : null}
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { padding: spacing.lg, backgroundColor: colors.paper, flexGrow: 1 },
  memberRow: { flexDirection: "row", alignItems: "center", paddingVertical: spacing.sm, gap: spacing.md },
  memberName: { color: colors.ink, fontSize: type.body, fontWeight: "600" },
  memberMeta: { color: colors.slate, fontSize: type.micro, marginTop: 2 },
  roleButton: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 2,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    backgroundColor: colors.white,
  },
  roleButtonText: { color: colors.ink, fontSize: type.micro, fontWeight: "600" },
  removeText: { color: colors.nomatch, fontSize: type.small, fontWeight: "600" },
  roleRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.md },
  rolePick: {
    flex: 1,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 2,
    backgroundColor: colors.white,
    paddingVertical: spacing.sm,
  },
  rolePickActive: { backgroundColor: colors.ink, borderColor: colors.ink },
  rolePickText: { color: colors.ink, fontSize: type.small, fontWeight: "600" },
});
