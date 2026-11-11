// Account: profile edit (name, marketing opt-in) + GDPR analytics consent.

import { useState } from "react";
import { ScrollView, StyleSheet, Switch, Text, View } from "react-native";

import { updateMe, useSession } from "../../features/auth";
import { useConsent, useRecordConsent } from "../../features/consent";
import { Button, ErrorNote, Field, Rule, SectionTitle } from "../../shared/ui/primitives";
import { colors, spacing, type } from "../../shared/ui/theme";

export default function AccountScreen() {
  const { user, refreshUser } = useSession();
  const { consent } = useConsent();
  const recordConsent = useRecordConsent();

  const [firstName, setFirstName] = useState(user?.first_name ?? "");
  const [lastName, setLastName] = useState(user?.last_name ?? "");
  const [marketing, setMarketing] = useState(user?.marketing_opt_in ?? false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const dirty =
    firstName !== user?.first_name ||
    lastName !== user?.last_name ||
    marketing !== user?.marketing_opt_in;

  const save = async () => {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await updateMe({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        marketing_opt_in: marketing,
      });
      await refreshUser();
      setSaved(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView style={{ backgroundColor: colors.paper }} contentContainerStyle={styles.screen}>
      <SectionTitle>Profile</SectionTitle>
      <Text style={styles.email}>{user?.email}</Text>
      <View style={{ height: spacing.md }} />
      <Field label="First name" value={firstName} onChangeText={setFirstName} />
      <Field label="Last name" value={lastName} onChangeText={setLastName} />
      <View style={styles.switchRow}>
        <Switch value={marketing} onValueChange={setMarketing} trackColor={{ true: colors.teal }} />
        <Text style={styles.switchLabel}>Product updates by email</Text>
      </View>
      <Button title={saved && !dirty ? "Saved ✓" : "Save"} onPress={save} busy={busy} disabled={!dirty} />
      <ErrorNote error={error} />

      <View style={{ height: spacing.xl }} />
      <Rule />
      <SectionTitle>Privacy</SectionTitle>
      <View style={styles.switchRow}>
        <Switch
          value={consent?.analytics ?? false}
          onValueChange={(value) => recordConsent.mutate(value)}
          trackColor={{ true: colors.teal }}
        />
        <Text style={styles.switchLabel}>Allow anonymous usage analytics</Text>
      </View>
      <Text style={styles.note}>
        {consent
          ? `Recorded ${new Date(consent.recorded_at).toLocaleDateString()} (policy ${consent.policy_version}).`
          : "No consent recorded yet — analytics stay off until you opt in."}
      </Text>
      {recordConsent.isError ? <ErrorNote error={recordConsent.error} /> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { padding: spacing.lg, backgroundColor: colors.paper, flexGrow: 1 },
  email: { color: colors.slate, fontSize: type.body },
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  switchLabel: { color: colors.ink, fontSize: type.body, flexShrink: 1 },
  note: { color: colors.slate, fontSize: type.small },
});
