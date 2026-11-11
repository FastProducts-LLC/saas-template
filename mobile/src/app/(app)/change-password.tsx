// Change password. Server revokes every session; the client helper persists
// the fresh token pair so THIS device stays signed in.

import { useState } from "react";
import { ScrollView, StyleSheet, Text } from "react-native";
import { useRouter } from "expo-router";

import { changePassword } from "../../features/auth";
import { ApiError } from "../../shared/api";
import { Button, ErrorNote, Field } from "../../shared/ui/primitives";
import { colors, spacing, type } from "../../shared/ui/theme";

export default function ChangePasswordScreen() {
  const router = useRouter();
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const fields = error instanceof ApiError ? error.fields : {};

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await changePassword({
        current_password: current,
        password,
        password_confirmation: confirmation,
      });
      router.back();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView style={{ backgroundColor: colors.paper }} contentContainerStyle={styles.screen}>
      <Text style={styles.note}>
        All other devices are signed out when you change your password.
      </Text>
      <ErrorNote error={error} />
      <Field
        label="Current password"
        value={current}
        onChangeText={setCurrent}
        secureTextEntry
        autoComplete="current-password"
        error={fields.current_password}
      />
      <Field
        label="New password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        autoComplete="new-password"
        error={fields.password}
      />
      <Field
        label="Confirm new password"
        value={confirmation}
        onChangeText={setConfirmation}
        secureTextEntry
        error={fields.password_confirmation}
      />
      <Button
        title="Change password"
        onPress={submit}
        busy={busy}
        disabled={!current || !password || !confirmation}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { padding: spacing.lg, backgroundColor: colors.paper, flexGrow: 1 },
  note: { color: colors.slate, fontSize: type.small, marginBottom: spacing.md },
});
