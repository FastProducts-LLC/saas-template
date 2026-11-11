// Auth guard + stack navigation. The tab group renders headerless; detail
// screens pushed on top get native headers with back buttons.

import { Redirect, Stack } from "expo-router";
import { ActivityIndicator, View } from "react-native";

import { useSession } from "../../features/auth";
import { colors } from "../../shared/ui/theme";

export default function AppLayout() {
  const { status } = useSession();

  if (status === "loading") {
    return (
      <View
        style={{
          flex: 1,
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: colors.paper,
        }}
      >
        <ActivityIndicator color={colors.tealDeep} />
      </View>
    );
  }
  if (status === "signedOut") return <Redirect href="/sign-in" />;

  return (
    <Stack
      screenOptions={{
        headerTintColor: colors.ink,
        headerStyle: { backgroundColor: colors.paper },
        headerShadowVisible: false,
        headerTitleStyle: { color: colors.ink, fontWeight: "700" },
        contentStyle: { backgroundColor: colors.paper },
      }}
    >
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="generation/[id]" options={{ title: "Generation" }} />
      <Stack.Screen name="llm/[id]" options={{ title: "Completion" }} />
      <Stack.Screen name="members" options={{ title: "Members" }} />
      <Stack.Screen name="api-keys" options={{ title: "API keys" }} />
      <Stack.Screen name="billing" options={{ title: "Billing" }} />
      <Stack.Screen name="account" options={{ title: "Account" }} />
      <Stack.Screen name="change-password" options={{ title: "Change password" }} />
    </Stack>
  );
}
