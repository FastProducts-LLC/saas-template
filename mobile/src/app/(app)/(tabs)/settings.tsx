// Settings hub: account links, org switcher/create, org admin screens, sign out.

import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import { useRouter, type Href } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { resendVerification, useSession } from "../../../features/auth";
import { canManageMembers, useCreateOrg, useCurrentOrg } from "../../../features/organizations";
import { Button, ErrorNote, Field, Rule, SectionTitle } from "../../../shared/ui/primitives";
import { colors, spacing, type } from "../../../shared/ui/theme";

export default function SettingsScreen() {
  const { user, signOut } = useSession();
  const { org, orgs, setOrgId } = useCurrentOrg();
  const insets = useSafeAreaInsets();

  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [intendedUse, setIntendedUse] = useState("");
  const [resent, setResent] = useState(false);
  const createOrg = useCreateOrg((orgId) => {
    setOrgId(orgId);
    setCreating(false);
    setName("");
    setIntendedUse("");
  });

  return (
    <ScrollView
      style={{ backgroundColor: colors.paper }}
      contentContainerStyle={{ padding: spacing.lg, paddingTop: insets.top + spacing.md }}
    >
      <Text style={styles.title}>Settings</Text>

      <SectionTitle>Account</SectionTitle>
      <Text style={styles.name}>{user?.name}</Text>
      <Text style={styles.meta}>{user?.email}</Text>
      {user && !user.email_verified ? (
        <View style={{ marginTop: spacing.sm }}>
          <Button
            title={resent ? "Verification email sent" : "Resend verification email"}
            variant="ghost"
            disabled={resent}
            onPress={async () => {
              await resendVerification();
              setResent(true);
            }}
          />
        </View>
      ) : null}
      <View style={{ height: spacing.sm }} />
      <NavRow title="Profile & privacy" href="/account" icon="user" />
      <NavRow title="Change password" href="/change-password" icon="lock" />
      <View style={{ height: spacing.md }} />
      <Rule />

      <SectionTitle>Organization</SectionTitle>
      {orgs.map((o) => {
        const active = o.id === org?.id;
        return (
          <Pressable key={o.id} onPress={() => setOrgId(o.id)} style={styles.orgRow}>
            <View style={{ flex: 1 }}>
              <Text style={[styles.orgName, active && { color: colors.tealDeep }]}>{o.name}</Text>
              <Text style={styles.meta}>{o.role}</Text>
            </View>
            {active ? <Feather name="check" size={18} color={colors.tealDeep} /> : null}
          </Pressable>
        );
      })}
      {orgs.length === 0 ? (
        <Text style={styles.meta}>You belong to no organization yet.</Text>
      ) : null}

      {creating ? (
        <View style={{ marginTop: spacing.md }}>
          <Field label="Organization name" value={name} onChangeText={setName} />
          <Field
            label="What will you use it for?"
            value={intendedUse}
            onChangeText={setIntendedUse}
          />
          <Button
            title="Create organization"
            busy={createOrg.isPending}
            disabled={!name.trim() || !intendedUse.trim()}
            onPress={() =>
              createOrg.mutate({ name: name.trim(), intended_use: intendedUse.trim() })
            }
          />
          {createOrg.isError ? <ErrorNote error={createOrg.error} /> : null}
        </View>
      ) : (
        <View style={{ marginTop: spacing.md }}>
          <Button title="New organization" variant="ghost" onPress={() => setCreating(true)} />
        </View>
      )}

      {org ? (
        <View>
          <View style={{ height: spacing.md }} />
          <NavRow title="Members & invitations" href="/members" icon="users" />
          <NavRow title="Billing & credits" href="/billing" icon="credit-card" />
          {canManageMembers(org.role) ? (
            <NavRow title="API keys" href="/api-keys" icon="key" />
          ) : null}
        </View>
      ) : null}

      <View style={{ height: spacing.xl }} />
      <Rule />
      <View style={{ marginTop: spacing.lg }}>
        <Button title="Sign out" variant="danger" onPress={signOut} />
      </View>
    </ScrollView>
  );
}

function NavRow({
  title,
  href,
  icon,
}: {
  title: string;
  href: Href;
  icon: React.ComponentProps<typeof Feather>["name"];
}) {
  const router = useRouter();
  return (
    <Pressable
      onPress={() => router.push(href)}
      style={({ pressed }) => [styles.navRow, pressed && { opacity: 0.6 }]}
    >
      <Feather name={icon} size={16} color={colors.slate} />
      <Text style={styles.navTitle}>{title}</Text>
      <Feather name="chevron-right" size={16} color={colors.slate} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  title: { fontSize: type.display, fontWeight: "700", color: colors.ink },
  name: { color: colors.ink, fontSize: type.title, fontWeight: "600" },
  meta: { color: colors.slate, fontSize: type.small, marginTop: 2 },
  orgRow: { flexDirection: "row", alignItems: "center", paddingVertical: spacing.sm },
  orgName: { color: colors.ink, fontSize: type.body, fontWeight: "600" },
  navRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.sm + 2,
  },
  navTitle: { flex: 1, color: colors.ink, fontSize: type.body, fontWeight: "500" },
});
