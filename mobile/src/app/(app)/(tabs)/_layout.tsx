import { Feather } from "@expo/vector-icons";
import { Tabs } from "expo-router";
import type React from "react";

import { colors } from "../../../shared/ui/theme";

type FeatherName = React.ComponentProps<typeof Feather>["name"];

// The active/inactive tints are our own theme strings, so resolve them from
// `focused` rather than forwarding the navigator's `color` — React Native
// 0.88 types that as an opaque ColorValue, which Feather's `color` rejects.
function tabIcon(name: FeatherName) {
  return function TabIcon({ focused, size }: { focused: boolean; size: number }) {
    return <Feather name={name} color={focused ? colors.tealDeep : colors.slate} size={size} />;
  };
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.tealDeep,
        tabBarInactiveTintColor: colors.slate,
        tabBarStyle: {
          backgroundColor: colors.white,
          borderTopColor: colors.line,
        },
      }}
    >
      {/* tabBarIcon's color is typed ColorValue since RN 0.88; ours are always
          the plain hex strings set in screenOptions above. */}
      <Tabs.Screen
        name="index"
        options={{
          title: "Dashboard",
          tabBarIcon: tabIcon("grid"),
        }}
      />
      <Tabs.Screen
        name="generations"
        options={{
          title: "Generate",
          tabBarIcon: tabIcon("zap"),
        }}
      />
      <Tabs.Screen
        name="llm"
        options={{
          title: "Text",
          tabBarIcon: tabIcon("message-square"),
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: "Settings",
          tabBarIcon: tabIcon("settings"),
        }}
      />
    </Tabs>
  );
}
