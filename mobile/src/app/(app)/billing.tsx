// Billing: credit packs → Stripe Checkout in the system browser, invoice
// history, customer portal. Wallet/invoices refetch when the app returns to
// the foreground so a completed purchase shows up on its own.

import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import {
  describePlan,
  formatPrice,
  useBillingPlan,
  useBillingPortal,
  useCheckout,
  useInvoices,
  usePacks,
  useRefetchOnForeground,
} from "../../features/billing";
import { useWallet } from "../../features/credits";
import { canManageMembers, useCurrentOrg } from "../../features/organizations";
import { Button, Empty, ErrorNote, Rule, SectionTitle, Stamp } from "../../shared/ui/primitives";
import { colors, spacing, type } from "../../shared/ui/theme";

export default function BillingScreen() {
  const { org } = useCurrentOrg();
  const isAdmin = canManageMembers(org?.role);
  const wallet = useWallet(org?.id);
  const billing = useBillingPlan(org?.id);
  const plan = billing.data ? describePlan(billing.data) : null;
  const packs = usePacks();
  const invoices = useInvoices(org?.id, isAdmin);
  const checkout = useCheckout(org?.id);
  const portal = useBillingPortal(org?.id);
  useRefetchOnForeground(org?.id);

  if (!org) {
    return (
      <View style={styles.screen}>
        <Empty message="Create an organization first." />
      </View>
    );
  }

  return (
    <ScrollView style={{ backgroundColor: colors.paper }} contentContainerStyle={styles.screen}>
      <View style={styles.balanceRow}>
        <Text style={styles.balance}>{wallet.data?.balance ?? "—"}</Text>
        <Text style={styles.balanceLabel}>credits available</Text>
      </View>
      <Rule />

      <SectionTitle>Current plan</SectionTitle>
      {billing.isPending ? <Text style={styles.note}>Loading plan…</Text> : null}
      {billing.isError ? <ErrorNote error={billing.error} /> : null}
      {plan ? (
        <View>
          <Text style={styles.packName}>{plan.title}</Text>
          <Text style={[styles.note, plan.tone === "warning" && { color: colors.nomatch }]}>
            {plan.subtitle}
          </Text>
        </View>
      ) : null}
      <Text style={styles.note}>Plans are managed in the web app.</Text>
      <Rule />

      <SectionTitle>Buy credits</SectionTitle>
      {!isAdmin ? (
        <Text style={styles.note}>Only org admins can purchase credits.</Text>
      ) : (
        <View>
          {(packs.data ?? [])
            .filter((p) => p.purchasable)
            .map((p) => (
              <View key={p.pack} style={styles.packRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.packName}>{p.name}</Text>
                  <Text style={styles.packMeta}>
                    {p.credits.toLocaleString()} credits · {formatPrice(p.unit_price_cents)}/credit
                    {p.discount_pct > 0 ? ` · save ${p.discount_pct}%` : ""}
                  </Text>
                </View>
                <Pressable
                  onPress={() => checkout.mutate(p.pack)}
                  disabled={checkout.isPending}
                  style={({ pressed }) => [
                    styles.buyButton,
                    (pressed || checkout.isPending) && { opacity: 0.6 },
                  ]}
                >
                  <Text style={styles.buyText}>{formatPrice(p.price_cents)}</Text>
                </Pressable>
              </View>
            ))}
          {checkout.isError ? <ErrorNote error={checkout.error} /> : null}
          <Text style={styles.note}>
            Payment opens in your browser. Credits appear here once Stripe confirms.
          </Text>
        </View>
      )}

      {isAdmin ? (
        <View>
          <SectionTitle>Invoices</SectionTitle>
          {(invoices.data ?? []).map((inv) => (
            <Pressable
              key={inv.id}
              onPress={() => inv.hosted_invoice_url && Linking.openURL(inv.hosted_invoice_url)}
              style={styles.invoiceRow}
            >
              <View style={{ flex: 1 }}>
                <Text style={styles.packName}>{inv.number ?? inv.id}</Text>
                <Text style={styles.packMeta}>{new Date(inv.created).toLocaleDateString()}</Text>
              </View>
              <Text style={styles.invoiceAmount}>
                {formatPrice(inv.amount_due, inv.currency)}
              </Text>
              <Stamp label={inv.status} tone={inv.status === "paid" ? "match" : "review"} />
            </Pressable>
          ))}
          {invoices.data?.length === 0 ? <Empty message="No invoices yet." /> : null}

          <View style={{ marginTop: spacing.lg }}>
            <Button
              title="Manage billing (Stripe portal)"
              variant="ghost"
              busy={portal.isPending}
              onPress={() => portal.mutate()}
            />
            {portal.isError ? <ErrorNote error={portal.error} /> : null}
          </View>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { padding: spacing.lg, backgroundColor: colors.paper, flexGrow: 1 },
  balanceRow: { flexDirection: "row", alignItems: "baseline", gap: spacing.sm, marginBottom: spacing.md },
  balance: { fontSize: 40, fontWeight: "700", color: colors.ink, fontVariant: ["tabular-nums"] },
  balanceLabel: { fontSize: type.small, color: colors.slate },
  packRow: { flexDirection: "row", alignItems: "center", paddingVertical: spacing.sm + 2, gap: spacing.md },
  packName: { color: colors.ink, fontSize: type.body, fontWeight: "600" },
  packMeta: { color: colors.slate, fontSize: type.micro, marginTop: 2 },
  buyButton: {
    backgroundColor: colors.ink,
    borderRadius: 2,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  buyText: { color: colors.white, fontWeight: "700", fontSize: type.small, fontVariant: ["tabular-nums"] },
  invoiceRow: { flexDirection: "row", alignItems: "center", paddingVertical: spacing.sm, gap: spacing.sm },
  invoiceAmount: { color: colors.ink, fontSize: type.small, fontWeight: "600", fontVariant: ["tabular-nums"] },
  note: { color: colors.slate, fontSize: type.small, marginTop: spacing.sm },
});
