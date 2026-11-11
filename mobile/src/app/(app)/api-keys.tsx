// API keys: list, create (raw key shown ONCE with copy), revoke.
// Creation/revocation are admin-gated server-side; the UI mirrors that.

import { formatLimit, isAtLimit, PLAN_LIMIT_MESSAGE, useEntitlements } from "../../features/entitlements";

import { useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";

import { useApiKeys, useCreateApiKey, useDeleteApiKey } from "../../features/api-keys";
import { canManageMembers, useCurrentOrg } from "../../features/organizations";
import { Button, Empty, ErrorNote, Field, Rule, SectionTitle } from "../../shared/ui/primitives";
import { colors, spacing, type } from "../../shared/ui/theme";

export default function ApiKeysScreen() {
  const { org } = useCurrentOrg();
  const entitlements = useEntitlements(org?.id);
  const entitlement = entitlements.data?.entitlements.find((item) => item.key === "api_keys");
  const atLimit = entitlement ? isAtLimit(entitlement) : false;
  const manage = canManageMembers(org?.role);
  const keys = useApiKeys(org?.id);

  const [name, setName] = useState("");
  const [freshKey, setFreshKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const create = useCreateApiKey(org?.id, (created) => {
    setFreshKey(created.raw_key);
    setCopied(false);
    setName("");
  });
  const remove = useDeleteApiKey(org?.id);

  if (!org) {
    return (
      <View style={styles.screen}>
        <Empty message="Create an organization first." />
      </View>
    );
  }

  const confirmRevoke = (keyId: string, keyName: string) => {
    Alert.alert(`Revoke "${keyName}"?`, "Requests using this key will fail immediately.", [
      { text: "Cancel", style: "cancel" },
      { text: "Revoke", style: "destructive", onPress: () => remove.mutate(keyId) },
    ]);
  };

  return (
    <ScrollView style={{ backgroundColor: colors.paper }} contentContainerStyle={styles.screen}>
      {entitlement ? (
        <Text style={styles.note}>
          API keys: {entitlement.used.toLocaleString()} / {formatLimit(entitlement.limit)}
        </Text>
      ) : null}
      {entitlements.isPending ? <Text style={styles.note}>Loading plan limits…</Text> : null}
      {entitlements.isError ? <ErrorNote error={entitlements.error} /> : null}
      {atLimit ? <Text style={styles.note}>{PLAN_LIMIT_MESSAGE}</Text> : null}

      {freshKey ? (
        <View style={styles.freshBlock}>
          <Text style={styles.freshTitle}>Copy this key now — it won't be shown again.</Text>
          <Text style={styles.freshKey} selectable>
            {freshKey}
          </Text>
          <View style={{ flexDirection: "row", gap: spacing.sm }}>
            <View style={{ flex: 1 }}>
              <Button
                title={copied ? "Copied ✓" : "Copy"}
                onPress={async () => {
                  await Clipboard.setStringAsync(freshKey);
                  setCopied(true);
                }}
              />
            </View>
            <View style={{ flex: 1 }}>
              <Button title="Done" variant="ghost" onPress={() => setFreshKey(null)} />
            </View>
          </View>
        </View>
      ) : null}

      <SectionTitle>Active keys</SectionTitle>
      {(keys.data ?? []).map((k) => (
        <View key={k.id} style={styles.keyRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.keyName}>{k.name}</Text>
            <Text style={styles.keyMeta}>
              {k.key_prefix}… · created {new Date(k.created_at).toLocaleDateString()}
            </Text>
          </View>
          {manage ? (
            <Pressable onPress={() => confirmRevoke(k.id, k.name)} hitSlop={8}>
              <Text style={styles.revokeText}>Revoke</Text>
            </Pressable>
          ) : null}
        </View>
      ))}
      {keys.data?.length === 0 ? <Empty message="No API keys yet." /> : null}
      {remove.isError ? <ErrorNote error={remove.error} /> : null}

      {manage ? (
        <View>
          <View style={{ height: spacing.md }} />
          <Rule />
          <SectionTitle>New key</SectionTitle>
          <Field label="Name" value={name} onChangeText={setName} placeholder="CI pipeline" />
          <Button
            title="Create key"
            busy={create.isPending}
            disabled={!name.trim() || !entitlement || atLimit}
            onPress={() => create.mutate(name.trim())}
          />
          {create.isError ? <ErrorNote error={create.error} /> : null}
          <Text style={styles.note}>
            Keys act with member-level access on this organization's API.
          </Text>
        </View>
      ) : (
        <Text style={styles.note}>Only org admins can create or revoke keys.</Text>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { padding: spacing.lg, backgroundColor: colors.paper, flexGrow: 1 },
  freshBlock: {
    borderWidth: 1,
    borderColor: colors.tealDeep,
    borderRadius: 2,
    padding: spacing.md,
    marginBottom: spacing.lg,
    backgroundColor: colors.white,
  },
  freshTitle: { color: colors.ink, fontSize: type.small, fontWeight: "700", marginBottom: spacing.sm },
  freshKey: {
    color: colors.tealDeep,
    fontSize: type.small,
    fontFamily: "Courier",
    marginBottom: spacing.md,
  },
  keyRow: { flexDirection: "row", alignItems: "center", paddingVertical: spacing.sm, gap: spacing.md },
  keyName: { color: colors.ink, fontSize: type.body, fontWeight: "600" },
  keyMeta: { color: colors.slate, fontSize: type.micro, marginTop: 2, fontVariant: ["tabular-nums"] },
  revokeText: { color: colors.nomatch, fontSize: type.small, fontWeight: "600" },
  note: { color: colors.slate, fontSize: type.small, marginTop: spacing.sm },
});
