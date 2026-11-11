import { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { Link, Redirect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useSession } from "../features/auth";
import { ApiError } from "../shared/api";
import { Button, ErrorNote, Field } from "../shared/ui/primitives";
import { colors, spacing, type } from "../shared/ui/theme";

export default function RegisterScreen() {
  const { status, register } = useSession();
  const insets = useSafeAreaInsets();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [marketingOptIn, setMarketingOptIn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [checkEmail, setCheckEmail] = useState(false);

  if (status === "signedIn") return <Redirect href="/" />;

  const fields = error instanceof ApiError ? error.fields : {};

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const verificationRequired = await register({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim(),
        password,
        password_confirmation: confirmation,
        terms_accepted: termsAccepted,
        marketing_opt_in: marketingOptIn,
      });
      if (verificationRequired) setCheckEmail(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  if (checkEmail) {
    // Same copy whether or not the address already had an account.
    return (
      <View
        style={[styles.container, { flex: 1, gap: spacing.md, paddingTop: insets.top + spacing.xl }]}
      >
        <Text style={styles.title}>Check your email</Text>
        <Text style={styles.footerText}>
          We have sent an email to {email.trim()}. Open the link in it to finish, then sign in.
        </Text>
        <Link href="/sign-in" style={styles.footerLink}>
          Back to sign in
        </Link>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        contentContainerStyle={[styles.container, { paddingTop: insets.top + spacing.xl }]}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.title}>Create account</Text>
        <ErrorNote error={error} />
        <Field
          label="First name"
          value={firstName}
          onChangeText={setFirstName}
          error={fields.first_name}
        />
        <Field
          label="Last name"
          value={lastName}
          onChangeText={setLastName}
          error={fields.last_name}
        />
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
          autoComplete="new-password"
          error={fields.password}
        />
        <Field
          label="Confirm password"
          value={confirmation}
          onChangeText={setConfirmation}
          secureTextEntry
          error={fields.password_confirmation}
        />
        <View style={styles.switchRow}>
          <Switch
            value={termsAccepted}
            onValueChange={setTermsAccepted}
            trackColor={{ true: colors.teal }}
          />
          <Text style={styles.switchLabel}>I accept the Terms of Service</Text>
        </View>
        <View style={styles.switchRow}>
          <Switch
            value={marketingOptIn}
            onValueChange={setMarketingOptIn}
            trackColor={{ true: colors.teal }}
          />
          <Text style={styles.switchLabel}>Send me product updates (optional)</Text>
        </View>
        <Button
          title="Create account"
          onPress={submit}
          busy={busy}
          disabled={!email || !password || !firstName || !termsAccepted}
        />
        <View style={styles.footer}>
          <Text style={styles.footerText}>Already registered? </Text>
          <Link href="/sign-in" style={styles.footerLink}>
            Sign in
          </Link>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.lg, backgroundColor: colors.paper, flexGrow: 1 },
  title: { fontSize: type.display, fontWeight: "700", color: colors.ink, marginBottom: spacing.lg },
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  switchLabel: { color: colors.ink, fontSize: type.body, flexShrink: 1 },
  footer: { flexDirection: "row", justifyContent: "center", marginTop: spacing.lg },
  footerText: { color: colors.slate, fontSize: type.body },
  footerLink: { color: colors.tealDeep, fontSize: type.body, fontWeight: "600" },
});
