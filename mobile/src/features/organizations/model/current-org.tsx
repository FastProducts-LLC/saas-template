// Current-organization selection, persisted across launches. Falls back to
// the first org when the stored id is gone (left/deleted org).

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import * as SecureStore from "expo-secure-store";

import { useSession } from "../../auth";
import { useOrgs } from "../api/hooks";
import type { Org } from "./types";

const CURRENT_ORG_KEY = "current_org_id";

interface CurrentOrgValue {
  org: Org | null;
  orgs: Org[];
  isLoading: boolean;
  setOrgId: (id: string) => void;
}

const CurrentOrgContext = createContext<CurrentOrgValue | null>(null);

export function CurrentOrgProvider({ children }: { children: ReactNode }) {
  const { status } = useSession();
  const { data: orgs = [], isLoading } = useOrgs(status === "signedIn");
  const [storedId, setStoredId] = useState<string | null>(null);

  useEffect(() => {
    SecureStore.getItemAsync(CURRENT_ORG_KEY).then(setStoredId);
  }, []);

  const setOrgId = useCallback((id: string) => {
    setStoredId(id);
    SecureStore.setItemAsync(CURRENT_ORG_KEY, id);
  }, []);

  const org = useMemo(
    () => orgs.find((o) => o.id === storedId) ?? orgs[0] ?? null,
    [orgs, storedId],
  );

  const value = useMemo(
    () => ({ org, orgs, isLoading, setOrgId }),
    [org, orgs, isLoading, setOrgId],
  );

  return <CurrentOrgContext.Provider value={value}>{children}</CurrentOrgContext.Provider>;
}

export function useCurrentOrg(): CurrentOrgValue {
  const ctx = useContext(CurrentOrgContext);
  if (!ctx) throw new Error("useCurrentOrg must be used inside CurrentOrgProvider");
  return ctx;
}
