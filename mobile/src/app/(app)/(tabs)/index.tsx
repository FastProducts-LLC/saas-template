// Dashboard: current org's credit wallet + recent activity.

import { FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useSession } from "../../../features/auth";
import { useCreditHistory, useWallet, type CreditTransaction } from "../../../features/credits";
import { useCurrentOrg } from "../../../features/organizations";
import { Empty, Rule, SectionTitle, Stamp } from "../../../shared/ui/primitives";
import { colors, spacing, type } from "../../../shared/ui/theme";

export default function DashboardScreen() {
  const { user } = useSession();
  const { org, isLoading: orgsLoading } = useCurrentOrg();
  const wallet = useWallet(org?.id);
  const history = useCreditHistory(org?.id, 15);
  const insets = useSafeAreaInsets();

  const refreshing = wallet.isRefetching || history.isRefetching;
  const refresh = () => {
    wallet.refetch();
    history.refetch();
  };

  return (
    <FlatList
      style={{ backgroundColor: colors.paper }}
      contentContainerStyle={{ padding: spacing.lg, paddingTop: insets.top + spacing.md }}
      data={history.data?.items ?? []}
      keyExtractor={(tx) => tx.id}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
      ListHeaderComponent={
        <View>
          <Text style={styles.kicker}>{org?.name ?? (orgsLoading ? "…" : "No organization")}</Text>
          <Text style={styles.greeting}>Hi {user?.first_name ?? "there"}</Text>

          {user && !user.email_verified ? (
            <View style={styles.verifyNote}>
              <Text style={styles.verifyText}>
                Verify your email to create organizations and start generating.
              </Text>
            </View>
          ) : null}

          {org ? (
            <View>
              <SectionTitle>Credits</SectionTitle>
              <View style={styles.walletRow}>
                <View style={styles.walletCell}>
                  <Text style={styles.walletValue}>{wallet.data?.balance ?? "—"}</Text>
                  <Text style={styles.walletLabel}>available</Text>
                </View>
                <View style={styles.walletCell}>
                  <Text style={styles.walletValue}>{wallet.data?.reserved ?? "—"}</Text>
                  <Text style={styles.walletLabel}>on hold</Text>
                </View>
                <View style={styles.walletCell}>
                  <Text style={styles.walletValue}>{wallet.data?.monthly_allowance ?? "—"}</Text>
                  <Text style={styles.walletLabel}>monthly</Text>
                </View>
              </View>
              <Rule />
              <SectionTitle>Recent activity</SectionTitle>
            </View>
          ) : (
            <Empty message="Create an organization in Settings to get started." />
          )}
        </View>
      }
      ListEmptyComponent={
        org && !history.isLoading ? <Empty message="No credit activity yet." /> : undefined
      }
      renderItem={({ item }) => <TransactionRow tx={item} />}
      ItemSeparatorComponent={Rule}
    />
  );
}

function TransactionRow({ tx }: { tx: CreditTransaction }) {
  const positive = tx.amount > 0;
  return (
    <View style={styles.txRow}>
      <View style={{ flex: 1 }}>
        <Text style={styles.txDescription} numberOfLines={1}>
          {tx.description ?? tx.action ?? tx.type}
        </Text>
        <Text style={styles.txMeta}>
          {new Date(tx.created_at).toLocaleString()}
          {tx.user_email ? ` · ${tx.user_email}` : ""}
        </Text>
      </View>
      <View style={styles.txAmountBlock}>
        <Text style={[styles.txAmount, { color: positive ? colors.match : colors.ink }]}>
          {positive ? "+" : ""}
          {tx.amount}
        </Text>
        <Stamp label={tx.type} tone={positive ? "match" : "neutral"} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  kicker: {
    fontSize: type.micro,
    fontWeight: "700",
    letterSpacing: 1.5,
    textTransform: "uppercase",
    color: colors.tealDeep,
  },
  greeting: { fontSize: type.display, fontWeight: "700", color: colors.ink, marginTop: spacing.xs },
  verifyNote: {
    borderLeftWidth: 2,
    borderLeftColor: colors.review,
    paddingLeft: spacing.md,
    marginTop: spacing.md,
  },
  verifyText: { color: colors.slate, fontSize: type.small },
  walletRow: { flexDirection: "row", marginBottom: spacing.md },
  walletCell: { flex: 1 },
  walletValue: {
    fontSize: type.display,
    fontWeight: "700",
    color: colors.ink,
    fontVariant: ["tabular-nums"],
  },
  walletLabel: { fontSize: type.micro, color: colors.slate, textTransform: "uppercase", letterSpacing: 1 },
  txRow: { flexDirection: "row", alignItems: "center", paddingVertical: spacing.sm + 2 },
  txDescription: { color: colors.ink, fontSize: type.body, fontWeight: "500" },
  txMeta: { color: colors.slate, fontSize: type.micro, marginTop: 2 },
  txAmountBlock: { alignItems: "flex-end", gap: 4, marginLeft: spacing.md },
  txAmount: { fontSize: type.body, fontWeight: "700", fontVariant: ["tabular-nums"] },
});
