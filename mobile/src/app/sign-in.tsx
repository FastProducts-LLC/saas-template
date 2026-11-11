import { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from "react-native";
import { Link, Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useSession } from "../features/auth";
import { ApiError } from "../shared/api";
import { BRAND } from "../shared/lib/brand";
import { Button, ErrorNote, Field } from "../shared/ui/primitives";
import { colors, spacing, type } from "../shared/ui/theme";

export default function SignInScreen() {
  const { status, signIn } = useSession();
  const insets = useSafeAreaInsets();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  if (status === "signedIn") return <Redirect href="/" />;

  const fields = error instanceof ApiError ? error.fields : {};

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await signIn(email.trim(), password);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        contentContainerStyle={[styles.container, { paddingTop: insets.top + spacing.xl }]}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.brand}>{BRAND.toUpperCase()}</Text>
        <Text style={styles.title}>Sign in</Text>
        <ErrorNote error={error} />
        <Field
          label="Email"
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          error={fields.email}
        />
        <Field
          label="Password"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoComplete="current-password"
          error={fields.password}
        />
        <Button title="Sign in" onPress={submit} busy={busy} disabled={!email || !password} />
        <View style={styles.footer}>
          <Text style={styles.footerText}>No account? </Text>
          <Link href="/register" style={styles.footerLink}>
            Create one
          </Link>
        </View>
        <View style={styles.footer}>
          <Link href="/forgot-password" style={styles.footerLink}>
            Forgot password?
          </Link>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.lg, backgroundColor: colors.paper, flexGrow: 1 },
  brand: {
    fontSize: type.micro,
    fontWeight: "700",
    letterSpacing: 2,
    color: colors.tealDeep,
    marginBottom: spacing.sm,
  },
  title: { fontSize: type.display, fontWeight: "700", color: colors.ink, marginBottom: spacing.lg },
  footer: { flexDirection: "row", justifyContent: "center", marginTop: spacing.lg },
  footerText: { color: colors.slate, fontSize: type.body },
  footerLink: { color: colors.tealDeep, fontSize: type.body, fontWeight: "600" },
});
