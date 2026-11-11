// Text completions: pick a provider, send a prompt (202), poll to a result.

import { useState } from "react";
import {
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { PROVIDERS, useComplete, useLlmCalls, type LlmCall, type LlmProvider } from "../../../features/llm";
import { useCurrentOrg } from "../../../features/organizations";
import { Button, Empty, ErrorNote, Rule, SectionTitle, Stamp } from "../../../shared/ui/primitives";
import { colors, spacing, type } from "../../../shared/ui/theme";

const STATUS_TONE = { pending: "review", succeeded: "match", failed: "nomatch" } as const;

export default function LlmScreen() {
  const { org } = useCurrentOrg();
  const calls = useLlmCalls(org?.id);
  const complete = useComplete(org?.id);
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const [provider, setProvider] = useState<LlmProvider>("gemini");
  const [prompt, setPrompt] = useState("");

  const submit = () => {
    if (!prompt.trim()) return;
    complete.mutate({ provider, prompt: prompt.trim() }, { onSuccess: () => setPrompt("") });
  };

  if (!org) {
    return (
      <View style={[styles.screen, { paddingTop: insets.top + spacing.md }]}>
        <Empty message="Create an organization in Settings first." />
      </View>
    );
  }

  return (
    <FlatList
      style={{ backgroundColor: colors.paper }}
      contentContainerStyle={{ padding: spacing.lg, paddingTop: insets.top + spacing.md }}
      data={calls.data ?? []}
      keyExtractor={(c) => c.id}
      refreshControl={<RefreshControl refreshing={calls.isRefetching} onRefresh={() => void calls.refetch()} />}
      ListHeaderComponent={
        <View>
          <Text style={styles.title}>Text</Text>
          <SectionTitle>Provider</SectionTitle>
          <View style={styles.providerRow}>
            {PROVIDERS.map((p) => {
              const active = p.value === provider;
              return (
                <Pressable
                  key={p.value}
                  onPress={() => setProvider(p.value)}
                  style={[styles.provider, active && styles.providerActive]}
                >
                  <Text style={[styles.providerText, active && { color: colors.white }]}>
                    {p.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          <SectionTitle>Prompt</SectionTitle>
          <TextInput
            style={styles.prompt}
            multiline
            value={prompt}
            onChangeText={setPrompt}
            placeholder="Ask anything…"
            placeholderTextColor={colors.slate}
            maxLength={8000}
          />
          <Button
            title="Send"
            onPress={submit}
            busy={complete.isPending}
            disabled={!prompt.trim()}
          />
          {complete.isError ? <ErrorNote error={complete.error} /> : null}
          <SectionTitle>History</SectionTitle>
        </View>
      }
      ListEmptyComponent={!calls.isLoading ? <Empty message="No completions yet." /> : undefined}
      renderItem={({ item }) => (
        <CallRow
          call={item}
          onPress={() => router.push({ pathname: "/llm/[id]", params: { id: item.id } })}
        />
      )}
      ItemSeparatorComponent={Rule}
    />
  );
}

function CallRow({ call, onPress }: { call: LlmCall; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.row, pressed && { opacity: 0.6 }]}>
      <View style={{ flex: 1 }}>
        <Text style={styles.rowPrompt} numberOfLines={1}>
          {call.prompt}
        </Text>
        <Text style={styles.rowMeta}>
          {call.model} · {call.credits_cost} cr · {new Date(call.created_at).toLocaleTimeString()}
        </Text>
      </View>
      <Stamp label={call.status} tone={STATUS_TONE[call.status]} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper, padding: spacing.lg },
  title: { fontSize: type.display, fontWeight: "700", color: colors.ink },
  providerRow: { flexDirection: "row", gap: spacing.sm },
  provider: {
    flex: 1,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 2,
    backgroundColor: colors.white,
    paddingVertical: spacing.sm,
  },
  providerActive: { backgroundColor: colors.ink, borderColor: colors.ink },
  providerText: { color: colors.ink, fontSize: type.small, fontWeight: "600" },
  prompt: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    borderRadius: 2,
    padding: spacing.md,
    minHeight: 88,
    textAlignVertical: "top",
    fontSize: type.body,
    color: colors.ink,
    marginBottom: spacing.md,
  },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: spacing.sm + 2, gap: spacing.md },
  rowPrompt: { color: colors.ink, fontSize: type.body, fontWeight: "500" },
  rowMeta: { color: colors.slate, fontSize: type.micro, marginTop: 2 },
});
