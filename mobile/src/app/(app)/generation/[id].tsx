// Generation detail: polls while pending, renders the result image when the
// asset is ready (authed download → data URI), cancel/delete actions.

import { Image, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";

import {
  useCancelGeneration,
  useDeleteGeneration,
  useGeneration,
  useGenerationFile,
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

export default function GenerationDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { org } = useCurrentOrg();
  const router = useRouter();

  const { data: generation, error } = useGeneration(org?.id, id);
  const file = useGenerationFile(org?.id, generation);
  const cancel = useCancelGeneration(org?.id);
  const remove = useDeleteGeneration(org?.id);

  if (error) {
    return (
      <View style={styles.screen}>
        <ErrorNote error={error} />
      </View>
    );
  }
  if (!generation) {
    return (
      <View style={styles.screen}>
        <Empty message="Loading…" />
      </View>
    );
  }

  const isImage = generation.mime_type?.startsWith("image/") ?? false;

  return (
    <ScrollView
      style={{ backgroundColor: colors.paper }}
      contentContainerStyle={styles.screen}
    >
      <View style={styles.headerRow}>
        <Text style={styles.meta}>
          {generation.kind} · {generation.model}
        </Text>
        <Stamp label={generation.status} tone={STATUS_TONE[generation.status]} />
      </View>

      <SectionTitle>Prompt</SectionTitle>
      <Text style={styles.prompt}>{generation.prompt}</Text>
      <Rule />

      <SectionTitle>Details</SectionTitle>
      <DetailRow label="Model" value={generation.model} />
      <DetailRow label="Cost" value={`${generation.credits_cost} credits`} />
      <DetailRow label="Created" value={new Date(generation.created_at).toLocaleString()} />
      {generation.completed_at ? (
        <DetailRow label="Completed" value={new Date(generation.completed_at).toLocaleString()} />
      ) : null}

      {generation.error ? (
        <View style={styles.failBlock}>
          <Text style={styles.failText}>{generation.error}</Text>
        </View>
      ) : null}

      {generation.status === "succeeded" && generation.has_file ? (
        <View>
          <SectionTitle>Result</SectionTitle>
          {isImage && file.data ? (
            <Image source={{ uri: file.data }} style={styles.image} resizeMode="contain" />
          ) : file.isLoading ? (
            <Empty message="Downloading result…" />
          ) : (
            <Text style={styles.meta}>
              Asset ready ({generation.mime_type ?? "binary"}) — view it on the web app.
            </Text>
          )}
        </View>
      ) : null}

      <View style={styles.actions}>
        {generation.status === "pending" ? (
          <Button
            title="Cancel"
            variant="ghost"
            busy={cancel.isPending}
            onPress={() => cancel.mutate(generation.id)}
          />
        ) : (
          <Button
            title="Delete"
            variant="danger"
            busy={remove.isPending}
            onPress={() => remove.mutate(generation.id, { onSuccess: () => router.back() })}
          />
        )}
      </View>
    </ScrollView>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flexGrow: 1, backgroundColor: colors.paper, padding: spacing.lg },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  prompt: { color: colors.ink, fontSize: type.body, lineHeight: 22, marginBottom: spacing.md },
  detailRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: spacing.xs },
  detailLabel: { color: colors.slate, fontSize: type.small },
  detailValue: { color: colors.ink, fontSize: type.small, fontWeight: "500" },
  failBlock: {
    borderLeftWidth: 2,
    borderLeftColor: colors.nomatch,
    paddingLeft: spacing.md,
    marginTop: spacing.md,
  },
  failText: { color: colors.slate, fontSize: type.small },
  image: {
    width: "100%",
    aspectRatio: 1,
    backgroundColor: colors.mist,
    borderRadius: 2,
  },
  meta: { color: colors.slate, fontSize: type.small },
  actions: { marginTop: spacing.xl, gap: spacing.sm },
});
