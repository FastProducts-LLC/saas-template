import type { ReactNode } from "react";
import { Alert } from "../../../shared/ui";
import { useEntitlement } from "../api/hooks";
import { isIncluded } from "../model/entitlements";
import type { EntitlementKey } from "../model/types";
import UpgradePrompt from "./UpgradePrompt";
export default function RequireEntitlement({
  entitlement,
  children,
}: {
  entitlement: EntitlementKey;
  children: ReactNode;
}) {
  const { data, isError } = useEntitlement(entitlement);
  if (isError) return <Alert tone="error">Unable to load entitlements.</Alert>;
  if (!data) return <p role="status">Loading entitlements…</p>;
  return isIncluded(data.limit) ? (
    children
  ) : (
    <UpgradePrompt entitlement={entitlement} limit={data.limit} />
  );
}
