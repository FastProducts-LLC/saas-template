// Completion detail: polls while pending, shows the response text and
// token/credit accounting when done.

import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";

import { useLlmCall } from "../../../features/llm";
import { useCurrentOrg } from "../../../features/organizations";
import { Empty, ErrorNote, Rule, SectionTitle, Stamp } from "../../../shared/ui/primitives";
import { colors, spacing, type } from "../../../shared/ui/theme";

const STATUS_TONE = { pending: "review", succeeded: "match", failed: "nomatch" } as const;

export default function LlmCallDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { org } = useCurrentOrg();
  const { data: call, error } = useLlmCall(org?.id, id);

  if (error) {
    return (
      <View style={styles.screen}>
        <ErrorNote error={error} />
      </View>
    );
  }
  if (!call) {
    return (
      <View style={styles.screen}>
        <Empty message="Loading…" />
      </View>
    );
  }

  return (
    <ScrollView style={{ backgroundColor: colors.paper }} contentContainerStyle={styles.screen}>
      <View style={styles.headerRow}>
        <Text style={styles.meta}>
          {call.provider} · {call.model}
        </Text>
        <Stamp label={call.status} tone={STATUS_TONE[call.status]} />
      </View>

      <SectionTitle>Prompt</SectionTitle>
      <Text style={styles.body}>{call.prompt}</Text>
      <Rule />

      {call.status === "pending" ? <Empty message="Waiting for the model…" /> : null}

      {call.response_text ? (
        <View>
          <SectionTitle>Response</SectionTitle>
          <Text style={styles.body} selectable>
            {call.response_text}
          </Text>
        </View>
      ) : null}

      {call.error ? (
        <View style={styles.failBlock}>
          <Text style={styles.failText}>{call.error}</Text>
        </View>
      ) : null}

      <SectionTitle>Accounting</SectionTitle>
      <Text style={styles.meta}>
        {call.tokens_in} tokens in · {call.tokens_out} tokens out · {call.credits_cost} credits
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { padding: spacing.lg, backgroundColor: colors.paper, flexGrow: 1 },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  body: { color: colors.ink, fontSize: type.body, lineHeight: 22, marginBottom: spacing.md },
  meta: { color: colors.slate, fontSize: type.small },
  failBlock: {
    borderLeftWidth: 2,
    borderLeftColor: colors.nomatch,
    paddingLeft: spacing.md,
    marginVertical: spacing.md,
  },
  failText: { color: colors.slate, fontSize: type.small },
});
