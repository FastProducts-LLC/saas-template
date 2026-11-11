// Forgot password: request the reset email. The link inside opens the web
// app's reset form (always 204 — account existence is never revealed).

import { useState } from "react";
import { ScrollView, StyleSheet, Text } from "react-native";
import { Link } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { forgotPassword } from "../features/auth";
import { Button, ErrorNote, Field } from "../shared/ui/primitives";
import { colors, spacing, type } from "../shared/ui/theme";

export default function ForgotPasswordScreen() {
  const insets = useSafeAreaInsets();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await forgotPassword(email.trim());
      setSent(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView
      contentContainerStyle={[styles.screen, { paddingTop: insets.top + spacing.xl }]}
      keyboardShouldPersistTaps="handled"
    >
      <Text style={styles.title}>Reset password</Text>
      {sent ? (
        <Text style={styles.note}>
          If an account exists for {email.trim()}, a reset link is on its way. Open it on this
          device or any browser, then sign in here with your new password.
        </Text>
      ) : (
        <Text style={styles.note}>
          Enter your account email and we'll send you a reset link.
        </Text>
      )}
      <ErrorNote error={error} />
      {!sent ? (
        <Field
          label="Email"
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
        />
      ) : null}
      {!sent ? (
        <Button title="Send reset link" onPress={submit} busy={busy} disabled={!email.trim()} />
      ) : null}
      <Link href="/sign-in" style={styles.backLink}>
        Back to sign in
      </Link>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { padding: spacing.lg, backgroundColor: colors.paper, flexGrow: 1 },
  title: { fontSize: type.display, fontWeight: "700", color: colors.ink, marginBottom: spacing.md },
  note: { color: colors.slate, fontSize: type.body, lineHeight: 21, marginBottom: spacing.lg },
  backLink: {
    color: colors.tealDeep,
    fontSize: type.body,
    fontWeight: "600",
    textAlign: "center",
    marginTop: spacing.lg,
  },
});
