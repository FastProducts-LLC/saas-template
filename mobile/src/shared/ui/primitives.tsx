// Minimal UI atoms shared by every screen. Structure comes from hairline
// rules and type (DESIGN.md) — no shadows, no colored chips.

import { type ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
  type TextInputProps,
} from "react-native";

import { ApiError, claimError, fieldLabel } from "../api";
import { colors, spacing, type } from "./theme";

export function Button({
  title,
  onPress,
  disabled,
  busy,
  variant = "primary",
}: {
  title: string;
  onPress: () => void;
  disabled?: boolean;
  busy?: boolean;
  variant?: "primary" | "ghost" | "danger";
}) {
  const inactive = disabled || busy;
  return (
    <Pressable
      onPress={onPress}
      disabled={inactive}
      style={({ pressed }) => [
        styles.button,
        variant === "primary" && styles.buttonPrimary,
        variant === "ghost" && styles.buttonGhost,
        variant === "danger" && styles.buttonDanger,
        (pressed || inactive) && { opacity: 0.6 },
      ]}
    >
      {busy ? (
        <ActivityIndicator
          size="small"
          color={variant === "primary" ? colors.white : colors.ink}
        />
      ) : (
        <Text
          style={[
            styles.buttonText,
            variant === "primary" && { color: colors.white },
            variant === "danger" && { color: colors.nomatch },
          ]}
        >
          {title}
        </Text>
      )}
    </Pressable>
  );
}

export function Field({
  label,
  error,
  ...input
}: TextInputProps & { label: string; error?: string }) {
  return (
    <View style={{ marginBottom: spacing.md }}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        placeholderTextColor={colors.slate}
        {...input}
        style={[styles.input, error ? { borderColor: colors.nomatch } : null]}
      />
      {error ? <Text style={styles.fieldError}>{error}</Text> : null}
    </View>
  );
}

/** Catalog-aware error block: headline + action step + support reference. */
/** Inline error: catalog headline, any per-field problems, one next step,
 * and the support ref. Rendering it claims the error, so the global toast
 * for the same failure is suppressed. */
export function ErrorNote({
  error,
  hideFields = false,
}: {
  error: unknown;
  hideFields?: boolean;
}) {
  claimError(error);
  if (!error) return null;
  if (typeof error === "string")
    return <Text style={styles.errorText}>{error}</Text>;
  if (!(error instanceof ApiError)) {
    return <Text style={styles.errorText}>Something went wrong.</Text>;
  }
  const fieldEntries = hideFields ? [] : Object.entries(error.fields);
  return (
    <View style={styles.errorBlock}>
      <Text style={styles.errorText}>{error.userMessage}</Text>
      {fieldEntries.map(([key, message]) => {
        const label = fieldLabel(key);
        return (
          <Text key={key} style={styles.errorAction}>
            {"• "}
            {label ? `${label}: ${message}` : message}
          </Text>
        );
      })}
      <Text style={styles.errorAction}>{error.actionStep}</Text>
      <Text style={styles.errorRef}>{error.reference}</Text>
    </View>
  );
}

/** Thin stamp — 1px border + text in a semantic color, per DESIGN.md. */
export function Stamp({
  label,
  tone,
}: {
  label: string;
  tone: "match" | "nomatch" | "review" | "neutral";
}) {
  const color =
    tone === "match"
      ? colors.match
      : tone === "nomatch"
        ? colors.nomatch
        : tone === "review"
          ? colors.review
          : colors.slate;
  return (
    <View style={[styles.stamp, { borderColor: color }]}>
      <Text style={[styles.stampText, { color }]}>{label.toUpperCase()}</Text>
    </View>
  );
}

export function Rule() {
  return <View style={styles.rule} />;
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <Text style={styles.sectionTitle}>{children}</Text>;
}

export function Empty({ message }: { message: string }) {
  return <Text style={styles.empty}>{message}</Text>;
}

const styles = StyleSheet.create({
  button: {
    alignItems: "center",
    justifyContent: "center",
    minHeight: 48,
    paddingHorizontal: spacing.lg,
    borderRadius: 2,
  },
  buttonPrimary: { backgroundColor: colors.ink },
  buttonGhost: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
  },
  buttonDanger: {
    borderWidth: 1,
    borderColor: colors.nomatch,
    backgroundColor: colors.white,
  },
  buttonText: { fontSize: type.body, fontWeight: "600", color: colors.ink },
  fieldLabel: {
    fontSize: type.micro,
    fontWeight: "700",
    letterSpacing: 1,
    textTransform: "uppercase",
    color: colors.slate,
    marginBottom: spacing.xs,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    borderRadius: 2,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    fontSize: type.body,
    color: colors.ink,
  },
  fieldError: {
    color: colors.nomatch,
    fontSize: type.small,
    marginTop: spacing.xs,
  },
  errorBlock: {
    borderLeftWidth: 2,
    borderLeftColor: colors.nomatch,
    paddingLeft: spacing.md,
    marginVertical: spacing.md,
  },
  errorText: { color: colors.ink, fontSize: type.body, fontWeight: "600" },
  errorAction: { color: colors.slate, fontSize: type.small, marginTop: 2 },
  errorRef: {
    color: colors.slate,
    fontSize: type.micro,
    marginTop: 2,
    fontVariant: ["tabular-nums"],
  },
  stamp: {
    borderWidth: 1,
    borderRadius: 2,
    paddingHorizontal: 6,
    paddingVertical: 1,
    alignSelf: "flex-start",
  },
  stampText: { fontSize: type.micro, fontWeight: "700", letterSpacing: 0.5 },
  rule: { height: StyleSheet.hairlineWidth, backgroundColor: colors.line },
  sectionTitle: {
    fontSize: type.micro,
    fontWeight: "700",
    letterSpacing: 1.2,
    textTransform: "uppercase",
    color: colors.slate,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  empty: {
    color: colors.slate,
    fontSize: type.body,
    paddingVertical: spacing.lg,
    textAlign: "center",
  },
});
