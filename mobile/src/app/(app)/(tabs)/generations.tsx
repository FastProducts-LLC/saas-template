// Create a generation (kind + prompt → 202) and watch the list poll to a
// terminal status. Costs come from the public credit catalog endpoint.

import { useMemo, useState } from "react";
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

import { useActionCosts } from "../../../features/credits";
import {
  useCreateGeneration,
  useGenerations,
  type Generation,
  type GenerationKind,
} from "../../../features/generations";
import { useCurrentOrg } from "../../../features/organizations";
import { Button, Empty, ErrorNote, Rule, SectionTitle, Stamp } from "../../../shared/ui/primitives";
import { colors, spacing, type } from "../../../shared/ui/theme";

const STATUS_TONE = {
  pending: "review",
  succeeded: "match",
  failed: "nomatch",
  canceled: "neutral",
} as const;

export default function GenerationsScreen() {
  const { org } = useCurrentOrg();
  const { data: costs } = useActionCosts();
  const generations = useGenerations(org?.id);
  const create = useCreateGeneration(org?.id);
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const kinds = useMemo(
    () => (costs ?? []).filter((c): c is typeof c & { action: GenerationKind } => c.action !== "llm_call"),
    [costs],
  );
  const [kind, setKind] = useState<GenerationKind | null>(null);
  const [prompt, setPrompt] = useState("");
  const selectedKind = kind ?? kinds[0]?.action ?? null;

  const submit = () => {
    if (!selectedKind || !prompt.trim()) return;
    create.mutate(
      { kind: selectedKind, prompt: prompt.trim() },
      { onSuccess: () => setPrompt("") },
    );
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
      data={generations.data ?? []}
      keyExtractor={(g) => g.id}
      refreshControl={
        <RefreshControl refreshing={generations.isRefetching} onRefresh={() => void generations.refetch()} />
      }
      ListHeaderComponent={
        <View>
          <Text style={styles.title}>Generate</Text>
          <SectionTitle>Type</SectionTitle>
          <View style={styles.kindRow}>
            {kinds.map((c) => {
              const active = c.action === selectedKind;
              return (
                <Pressable
                  key={c.action}
                  onPress={() => setKind(c.action)}
                  style={[styles.kind, active && styles.kindActive]}
                >
                  <Text style={[styles.kindName, active && { color: colors.white }]}>{c.name}</Text>
                  <Text style={[styles.kindCost, active && { color: colors.mist }]}>
                    {c.cost} cr
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
            placeholder="Describe what to generate…"
            placeholderTextColor={colors.slate}
            maxLength={4000}
          />
          <Button
            title="Generate"
            onPress={submit}
            busy={create.isPending}
            disabled={!selectedKind || !prompt.trim()}
          />
          {create.isError ? <ErrorNote error={create.error} /> : null}
          <SectionTitle>History</SectionTitle>
        </View>
      }
      ListEmptyComponent={!generations.isLoading ? <Empty message="Nothing generated yet." /> : undefined}
      renderItem={({ item }) => (
        <GenerationRow
          generation={item}
          onPress={() => router.push({ pathname: "/generation/[id]", params: { id: item.id } })}
        />
      )}
      ItemSeparatorComponent={Rule}
    />
  );
}

function GenerationRow({ generation, onPress }: { generation: Generation; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.row, pressed && { opacity: 0.6 }]}>
      <View style={{ flex: 1 }}>
        <Text style={styles.rowPrompt} numberOfLines={1}>
          {generation.prompt}
        </Text>
        <Text style={styles.rowMeta}>
          {generation.model} · {generation.credits_cost} cr ·{" "}
          {new Date(generation.created_at).toLocaleTimeString()}
        </Text>
      </View>
      <Stamp label={generation.status} tone={STATUS_TONE[generation.status]} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper, padding: spacing.lg },
  title: { fontSize: type.display, fontWeight: "700", color: colors.ink },
  kindRow: { flexDirection: "row", gap: spacing.sm },
  kind: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 2,
    backgroundColor: colors.white,
    padding: spacing.sm,
  },
  kindActive: { backgroundColor: colors.ink, borderColor: colors.ink },
  kindName: { color: colors.ink, fontSize: type.small, fontWeight: "600" },
  kindCost: { color: colors.slate, fontSize: type.micro, marginTop: 2 },
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
