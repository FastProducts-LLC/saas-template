// Global error surface: subscribes to the error bus and shows the catalog's
// user copy as a transient banner. Field-display errors are skipped — forms
// bind those inline via ApiError.fields.

import { useCallback, useEffect, useRef, useState } from "react";
import { Animated, StyleSheet, Text } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  INLINE_CLAIM_GRACE_MS,
  isErrorClaimed,
  subscribeErrors,
  type ApiError,
} from "../api";
import { colors, spacing, type } from "./theme";

const VISIBLE_MS = 4500;

export function ErrorToastHost() {
  const [error, setError] = useState<ApiError | null>(null);
  const opacity = useRef(new Animated.Value(0)).current;
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const insets = useSafeAreaInsets();

  const show = useCallback(
    (err: ApiError) => {
      setError(err);
      Animated.timing(opacity, {
        toValue: 1,
        duration: 150,
        useNativeDriver: true,
      }).start();
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        Animated.timing(opacity, {
          toValue: 0,
          duration: 250,
          useNativeDriver: true,
        }).start(() => setError(null));
      }, VISIBLE_MS);
    },
    [opacity],
  );

  useEffect(
    () =>
      subscribeErrors((err) => {
        if (err.display === "field") return;
        // Wait for a screen to claim it inline (<ErrorNote>) before toasting.
        setTimeout(() => {
          if (!isErrorClaimed(err)) show(err);
        }, INLINE_CLAIM_GRACE_MS);
      }),
    [show],
  );

  if (!error) return null;
  return (
    <Animated.View
      pointerEvents="none"
      style={[styles.toast, { top: insets.top + spacing.sm, opacity }]}
    >
      <Text style={styles.message}>{error.userMessage}</Text>
      <Text style={styles.reference}>{error.reference}</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  toast: {
    position: "absolute",
    left: spacing.md,
    right: spacing.md,
    backgroundColor: colors.ink,
    borderRadius: 2,
    padding: spacing.md,
    zIndex: 100,
  },
  message: { color: colors.white, fontSize: type.body, fontWeight: "600" },
  reference: { color: colors.mist, fontSize: type.micro, marginTop: 2 },
});
